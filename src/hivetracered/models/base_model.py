import asyncio
import contextlib
import warnings
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from abc import ABC, abstractmethod


class Model(ABC):
    """
    Abstract base class for language model implementations.
    Defines the standard interface for interacting with various LLM providers,
    supporting both synchronous and asynchronous operations for single requests and batches.
    """
    model_name: str
    max_concurrency: int = 0

    def _concurrency_slot(self) -> AbstractAsyncContextManager:
        """Acquire one concurrency slot for an async call.

        Lazily constructs a per-instance ``asyncio.Semaphore`` capped at
        ``self.max_concurrency``. The semaphore binds to the running event loop
        on first acquire; if the model is reused across event loops, the slot
        is reconstructed for the new loop.

        Returns ``contextlib.nullcontext()`` when ``max_concurrency == 0``
        (unlimited). Subclasses' ``ainvoke`` implementations must wrap their
        outbound request with ``async with self._concurrency_slot():`` so that
        every async entry point (``ainvoke``, ``abatch``, ``stream_abatch``)
        observes the per-model cap.
        """
        if self.max_concurrency == 0:
            return contextlib.nullcontext()
        sem = getattr(self, "_concurrency_sem", None)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrency)
            self._concurrency_sem = sem
        return sem

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

