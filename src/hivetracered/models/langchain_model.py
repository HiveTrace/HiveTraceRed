from typing import Any
from hivetracered.models.base_model import Model
from collections.abc import AsyncGenerator
import asyncio
from tqdm import tqdm
from abc import abstractmethod

from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain.schema import LLMResult

class LangchainModel(Model):
    """
    Generic LangChain language model wrapper.
    Provides synchronous and asynchronous methods for single and batch requests.
    Can be used with any LangChain model implementation.
    
    This is an abstract base class. Child classes only need to implement the __init__ method
    to configure the specific LangChain model they're wrapping.
    """
    
    @abstractmethod
    def __init__(self, model_name: str, max_concurrency: int = 0, max_retries: int = 3, **kwargs):
        """
        Initialize the LangChain model wrapper.

        Args:
            model_name: Name/identifier of the model
            max_concurrency: Maximum number of concurrent requests (0 for unlimited)
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional keyword arguments for the model

        Note:
            Child classes must implement this method to initialize:
            - self.model_name = model_name
            - self.max_concurrency = max_concurrency
            - self.batch_size = self.max_concurrency  # For backward compatibility
            - self.max_retries = max_retries
            - self.kwargs = kwargs
            - self.client = <the actual LangChain model instance>

            After creating the client, wrap it with retry logic:
            - self.client = self._add_retry_policy(self.client)
        """
        pass

    @staticmethod
    def _make_rate_limiter(rpm: int, max_bucket_size: int | None = None) -> InMemoryRateLimiter:
        """
        Build an InMemoryRateLimiter from a requests-per-minute setting.

        Args:
            rpm: Target rate in requests per minute. Clamped to a minimum of 1
                so a misconfigured 0 still produces a usable limiter.
            max_bucket_size: Optional burst capacity for the token bucket.

        Returns:
            Configured InMemoryRateLimiter instance.
        """
        kwargs: dict[str, Any] = {
            "requests_per_second": max(1, rpm) / 60,
            "check_every_n_seconds": 0.1,
        }
        if max_bucket_size is not None:
            kwargs["max_bucket_size"] = max_bucket_size
        return InMemoryRateLimiter(**kwargs)

    def _add_retry_policy(self, client):
        """
        Wrap the LangChain client with retry policy for transient errors.

        Retries on:
        - Connection errors (network failures)
        - Timeout errors
        - 5xx server errors
        - 429 rate limit errors

        Uses exponential backoff with jitter to prevent thundering herd.

        Args:
            client: The LangChain model client to wrap

        Returns:
            Client wrapped with retry policy
        """
        return client.with_retry(
            stop_after_attempt=self.max_retries,
            wait_exponential_jitter=True,
            retry_if_exception_type=(
                # Network/connection errors
                ConnectionError,
                TimeoutError,
                # # LangChain doesn't raise exceptions by default, but handle if they do
                # Exception,
            ),
        )

    def invoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model synchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            The model's response
        """
        return dict(self.client.invoke(prompt))
    
    async def ainvoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model asynchronously.

        Args:
            prompt: A string or list of messages to send to the model

        Returns:
            The model's response
        """
        async with self._concurrency_slot():
            return dict(await self.client.ainvoke(prompt))
    
    def batch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model synchronously.

        Args:
            prompts: A list of prompts to send to the model

        Returns:
            A list of model responses
        """
        if self.max_concurrency == 0:
            return [dict(response) for response in self.client.batch(prompts)]
        else:
            return [dict(response) for response in self.client.batch(prompts, config={"max_concurrency": self.max_concurrency})]
    
    async def abatch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model asynchronously.

        Args:
            prompts: A list of prompts to send to the model

        Returns:
            A list of model responses
        """
        # Concurrency is enforced inside ainvoke via self._concurrency_slot();
        # asyncio.gather lets every prompt acquire a slot independently and
        # the cap holds whether or not other batches are running concurrently.
        return list(await asyncio.gather(*(self.ainvoke(p) for p in prompts)))

    def is_answer_blocked(self, answer: dict) -> bool:
        """
        Check if the answer is blocked by guardrails.
        Different LangChain models may have different mechanisms for indicating blocked responses.
        
        Returns:
            Boolean indicating if the answer was blocked
        """
        if "response_metadata" in answer and "finish_reason" in answer["response_metadata"]:
            return answer["response_metadata"]["finish_reason"] == "blacklist"
        return False

    def get_params(self) -> dict:
        """
        Get the parameters of the model.
        
        Returns:
            Dictionary with model parameters
        """
        return {
            **self.client.dict(),
            "max_concurrency": self.max_concurrency,
            "batch_size": self.batch_size
        }
    
    async def stream_abatch(self, prompts: list[str | list[dict[str, str]]]) -> AsyncGenerator[dict, None]:
        """
        Send multiple requests to the model asynchronously and yield results as they complete.

        Args:
            prompts: A list of prompts to send to the model

        Returns:
            An async generator of model responses in order of completion
        """
        async def task(idx, prompt):
            # Concurrency is enforced inside ainvoke via self._concurrency_slot().
            try:
                result = await self.ainvoke(prompt)
                return idx, result, None
            except Exception as e:
                error_response = {
                    "content": "",
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
                return idx, error_response, e

        tasks = [asyncio.create_task(task(i, inp)) for i, inp in enumerate(prompts)]
        total_tasks = len(tasks)

        results = dict()
        cur_result_idx = 0

        # Create tqdm progress bar with context manager for proper cleanup
        with tqdm(total=total_tasks, desc=f"Processing requests with {self.model_name}", unit="request") as progress_bar:
            for task in asyncio.as_completed(tasks):
                idx, res, error = await task
                progress_bar.update(1)  # Update progress bar for each completed task

                results[idx] = res
                while cur_result_idx in results:
                    yield dict(results[cur_result_idx])
                    results.pop(cur_result_idx)
                    cur_result_idx += 1 


class BatchCallback(BaseCallbackHandler):
    def __init__(self, total: int):
        super().__init__()
        self.count = 0
        self.progress_bar = tqdm(total=total)  # define a progress bar
        
    # Override on_llm_end method. This is called after every response from LLM
    def on_llm_end(self, response: LLMResult, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self.count += 1
        self.progress_bar.update(1)
        
    def __enter__(self):
        self.progress_bar.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.progress_bar.__exit__(exc_type, exc_value, exc_traceback)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        return self.__exit__(exc_type, exc_value, exc_traceback)

    def __del__(self):
        self.progress_bar.__del__()