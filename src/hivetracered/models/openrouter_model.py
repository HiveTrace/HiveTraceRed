from typing import List, Any, Optional, Union, Dict
from hivetracered.models.openai_model import OpenAIModel
from langchain_openai import ChatOpenAI
from hivetracered.models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os
from typing import AsyncGenerator
import asyncio
from tqdm import tqdm
import warnings

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import RunnableLambda

load_dotenv(override=True)

class OpenRouterModel(LangchainModel):
    """
    OpenAI language model implementation using the LangChain integration.
    Provides a standardized interface to OpenAI's API with rate limiting support and 
    both synchronous and asynchronous processing capabilities.
    """
    
    def __init__(self, model: str = "nvidia/nemotron-nano-9b-v2", base_url = "https://openrouter.ai/api/v1", max_concurrency: Optional[int] = None, batch_size: Optional[int] = None, rpm: int = 300, api_key: str = None, max_retries: int = 3, **kwargs):

        """
        Initialize the OpenAI model client with the specified configuration.

        Args:
            model: OpenAI model identifier (e.g., "nvidia/nemotron-nano-9b-v2")
            base_url: OpenRouter API base URL
            max_concurrency: Maximum number of concurrent requests (replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            rpm: Rate limit in requests per minute
            api_key: API key; defaults to OPENROUTER_API_KEY env var
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters to pass to the ChatOpenAI constructor
        """
        load_dotenv(override=True)

        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.model_name = model
        self.max_retries = max_retries

        # Handle deprecation
        if batch_size is not None:
            warnings.warn(
                "The 'batch_size' parameter is deprecated and will be removed in v2.0.0. "
                "Use 'max_concurrency' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            if max_concurrency is None:
                max_concurrency = batch_size

        # Set default if neither provided
        if max_concurrency is None:
            max_concurrency = 1

        self.max_concurrency = max_concurrency
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}

        if not "temperature" in self.kwargs:
            self.kwargs["temperature"] = 0.000001
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=rpm / 60,
            check_every_n_seconds=0.1,
        )
        self.client = ChatOpenAI(model=model, rate_limiter=rate_limiter, base_url=base_url, openai_api_key=api_key, **self.kwargs)
        self.client = self._add_retry_policy(self.client)
    