import asyncio
import contextlib
import inspect
from hivetracered.models.resources import register_model
import warnings
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from abc import ABC, abstractmethod

# Near-zero temperature for providers whose API rejects a literal 0.
TEMPERATURE_EPSILON = 1e-6


class Model(ABC):
    """
    Abstract base class for language model implementations.
    Defines the standard interface for interacting with various LLM providers,
    supporting both synchronous and asynchronous operations for single requests and batches.
    """
    model_name: str
    max_concurrency: int = 0

    # False for providers whose temperature range excludes 0 (the judge then
    # gets TEMPERATURE_EPSILON instead of 0.0). See config._force_judge_temperature.
    SUPPORTS_ZERO_TEMPERATURE: bool = True

    # Stateful SDK transports may only be used and closed on one event loop.
    _loop_affine_resources = False

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._closed = False
        instance._request_loop = None
        instance._pending_requests = set()
        instance._cleanup_callbacks = []
        # Register before __init__: a constructor may allocate clients and then fail.
        register_model(instance)
        return instance

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("Model is closed; create a new model for another run")

    def _add_cleanup(self, callback):
        self._cleanup_callbacks.append(callback)

    async def _cancel_requests(self):
        current = asyncio.current_task()
        pending = [task for task in self._pending_requests if task is not current and not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def aclose(self):
        """Cancel pending requests and close owned resources before their loop exits.

        Caller-supplied transports are not owned and are never closed here.
        Repeated calls are safe. Models must not be used after closing.
        """
        if self._closed:
            return
        loop = asyncio.get_running_loop()
        if self._loop_affine_resources and self._request_loop is not None and self._request_loop is not loop:
            raise RuntimeError("Close the model on the event loop where it was used")
        self._closed = True
        await self._cancel_requests()
        errors = []
        callbacks, self._cleanup_callbacks = self._cleanup_callbacks, []
        for callback in reversed(callbacks):
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    async def __aenter__(self):
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    @contextlib.asynccontextmanager
    async def _concurrency_slot(self) -> AbstractAsyncContextManager:
        """Track queued and active requests and enforce the per-model cap.

        Semaphores are rebuilt when the loop changes. Stateful SDK transports
        additionally reject reuse in another loop: rebuilding a semaphore cannot
        make a live HTTP connection safe to transfer.
        """
        self._ensure_open()
        loop = asyncio.get_running_loop()
        if self._loop_affine_resources:
            if self._request_loop is not None and self._request_loop is not loop:
                raise RuntimeError("Model belongs to another event loop; create a new model")
            self._request_loop = loop
        if getattr(self, "_concurrency_sem_loop", None) is not loop:
            self._concurrency_sem = asyncio.Semaphore(self.max_concurrency) if self.max_concurrency else None
            self._concurrency_sem_loop = loop
        task = asyncio.current_task()
        self._pending_requests.add(task)
        try:
            async with self._concurrency_sem if self._concurrency_sem is not None else contextlib.nullcontext():
                yield
        finally:
            self._pending_requests.discard(task)

    @abstractmethod
    def invoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model synchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with at least a 'content' key
        """
        pass
    
    @abstractmethod
    async def ainvoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model asynchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with at least a 'content' key
        """
        pass
    
    @abstractmethod
    def batch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model synchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
        """
        pass
    
    @abstractmethod
    async def abatch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model asynchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
        """
        pass
    
    def is_answer_blocked(self, answer: dict) -> bool:
        """
        Check if the answer is blocked by model's safety guardrails.
        
        Args:
            answer: The model response dictionary to check
            
        Returns:
            Boolean indicating if the response was blocked
        """
        return False
    
    def get_params(self) -> dict:
        """
        Get the parameters of the model.
        
        Returns:
            Dictionary containing the model's configuration parameters
        """
        return self.__dict__
    
    @staticmethod
    def _ssl_verify(verify_ssl: bool | str):
        """
        Normalize a verify_ssl setting (bool or CA-bundle path) to an
        httpx-compatible verify value. A path is converted to an SSLContext
        because httpx>=0.28 deprecates passing paths directly.
        """
        if isinstance(verify_ssl, str):
            import ssl
            return ssl.create_default_context(cafile=verify_ssl)
        return verify_ssl

    @staticmethod
    def _resolve_concurrency(
        max_concurrency: int | None,
        batch_size: int | None,
        default: int,
    ) -> int:
        """
        Resolve effective concurrency, honoring the deprecated `batch_size` alias.

        Emits DeprecationWarning if batch_size is provided. When both are set,
        max_concurrency wins. Falls back to `default` when neither is provided.
        """
        if batch_size is not None:
            warnings.warn(
                "The 'batch_size' parameter is deprecated and will be removed in v2.0.0. "
                "Use 'max_concurrency' instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            if max_concurrency is None:
                max_concurrency = batch_size

        if max_concurrency is None:
            max_concurrency = default

        return max_concurrency

    @abstractmethod
    async def stream_abatch(self, prompts: list[str | list[dict[str, str]]]) -> AsyncGenerator[dict, None]:
        """
        Send multiple requests to the model asynchronously and yield results as they complete.
        
        Args:
            prompts: A list of prompts to send to the model

        Yields:
            Response dictionaries. Implementations MUST yield results in the same order
            as the input prompts list, since downstream stages match responses to prompts
            by sequential index.
        """
        pass

