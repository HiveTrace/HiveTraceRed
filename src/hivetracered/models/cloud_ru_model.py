from typing import Any, Optional
from langchain_openai import ChatOpenAI
from hivetracered.models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os
import warnings

from langchain_core.rate_limiters import InMemoryRateLimiter


class CloudRuModel(LangchainModel):
    """
    Sber Cloud model implementation using LangChain's OpenAI-compatible integration.
    Routes requests to Cloud.ru Foundation Models OpenAI API.
    """

    def __init__(
        self,
        model: str = "GigaChat/GigaChat-2-Max",
        max_concurrency: Optional[int] = None,
        batch_size: Optional[int] = None,
        rpm: int = 60,
        api_key: str = None,
        base_url: str = "https://foundation-models.api.cloud.ru/v1",
        max_retries: int = 3,
        **kwargs: Any,
    ):
        """
        Initialize the Sber Cloud LangChain client.

        Args:
            model: Model identifier, e.g. "GigaChat/GigaChat-2-Max".
            max_concurrency: Maximum number of concurrent requests (replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            rpm: Requests-per-minute soft limit enforced client-side.
            api_key: API key; defaults to GIGACHAT_CLOUD_API_KEY env var.
            base_url: Override API base URL; defaults to Cloud.ru endpoint.
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Passed to ChatOpenAI (e.g., temperature, max_tokens, top_p).
        """
        load_dotenv(override=True)

        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("SBER_CLOUD_API_KEY")

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

        # Defaults
        self.kwargs = kwargs or {}
        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        # Simple client-side rate limiting (same approach as OpenAIModel)
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=max(1, rpm) / 60,
            check_every_n_seconds=0.1,
            max_bucket_size=self.max_concurrency,
        )

        # LangChain ChatOpenAI supports OpenAI-compatible endpoints via base_url
        self.client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            rate_limiter=rate_limiter,
            **self.kwargs,
        )
        self.client = self._add_retry_policy(self.client)


