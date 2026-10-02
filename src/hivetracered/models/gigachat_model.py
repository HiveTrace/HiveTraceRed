from langchain_gigachat import GigaChat
from hivetracered.models.langchain_model import LangchainModel
import os
from dotenv import load_dotenv
from hivetracered.registry import Registry

@Registry.model()
class GigaChatModel(LangchainModel):
    """
    GigaChat language model implementation using LangChain integration.
    Provides standardized access to Sber's GigaChat models with support for
    both synchronous and asynchronous request processing.
    """

    # GigaChat requires temperature > 0; the judge gets TEMPERATURE_EPSILON instead.
    SUPPORTS_ZERO_TEMPERATURE = False

    def __init__(self, model: str = "GigaChat", max_concurrency: int | None = None, batch_size: int | None = None, scope: str | None = None, credentials: str | None = None, verify_ssl_certs: bool = False, max_retries: int = 3, **kwargs):
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

        self.max_concurrency = self._resolve_concurrency(max_concurrency, batch_size, default=1)
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}
        self.client = GigaChat(credentials=credentials, model=model, scope=scope, verify_ssl_certs=verify_ssl_certs, **self.kwargs)
        raw_client = self.client
        async def close_sdk():
            # GigaChat initializes its SDK lazily; do not create it just to close it.
            sdk = raw_client.__dict__.get("_client")
            if sdk is not None:
                await sdk.aclose()
        self._add_cleanup(close_sdk)
        self.client = self._add_retry_policy(self.client)

    