from typing import List, Any, Optional, Union, Dict
from langchain_gigachat import GigaChat
from hivetracered.models.langchain_model import LangchainModel
import os
from dotenv import load_dotenv
import warnings

class GigaChatModel(LangchainModel):
    """
    GigaChat language model implementation using LangChain integration.
    Provides standardized access to Sber's GigaChat models with support for
    both synchronous and asynchronous request processing.
    """
    
    def __init__(self, model: str = "GigaChat", max_concurrency: Optional[int] = None, batch_size: Optional[int] = None, scope: str = None, credentials: str = None, verify_ssl_certs: bool = False, max_retries: int = 3, **kwargs):
        """
        Initialize the GigaChat model client with the specified configuration.

        Args:
            model: GigaChat model variant (e.g., "GigaChat", "GigaChat-Pro")
            max_concurrency: Maximum number of concurrent requests (replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            scope: API scope for authorization (from env or explicit)
            credentials: API credentials for authentication (from env or explicit)
            verify_ssl_certs: Whether to verify SSL certificates for API connections
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters for model configuration:
                     - profanity_check: Whether to enable profanity filtering
                     - temperature: Sampling temperature (lower = more deterministic)
                     - max_tokens: Maximum tokens in generated responses
                     - top_p: Top-p sampling parameter for response diversity
        """
        load_dotenv(override=True)

        # Get credentials from environment if not provided
        if scope is None:
            scope = os.getenv("GIGACHAT_API_SCOPE")
        if credentials is None:
            credentials = os.getenv("GIGACHAT_CREDENTIALS")
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
        self.client = GigaChat(credentials=credentials, model=model, scope=scope, verify_ssl_certs=verify_ssl_certs, **self.kwargs)
        self.client = self._add_retry_policy(self.client)

    