from hivetracered.models.langchain_model import LangchainModel
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from hivetracered.registry import Registry

@Registry.model()
class GeminiModel(LangchainModel):
    """
    Google Gemini language model implementation using LangChain integration.
    Provides standardized access to Google's Gemini models with built-in rate limiting
    and support for both synchronous and asynchronous operations.
    """

    def __init__(self, model: str = "gemini-2.5-flash", max_concurrency: int | None = None, batch_size: int | None = None, rpm: int = 10, max_retries: int = 3, verify_ssl: bool | str = True, **kwargs):
        """
        Initialize the Gemini model client with the specified configuration.

        Args:
            model: Gemini model identifier (e.g., "gemini-1.5-pro", "gemini-2.5-flash")
            max_concurrency: Maximum number of concurrent requests (0 for unlimited, replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            rpm: Rate limit in requests per minute
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            verify_ssl: True (default) to verify TLS certificates, False to disable
                verification, or a path to a custom CA bundle
            **kwargs: Additional parameters for model configuration:
                     - temperature: Sampling temperature (lower = more deterministic)
                     - top_p: Top-p sampling parameter for response diversity
                     - top_k: Top-k sampling parameter for response diversity
                     - max_output_tokens: Maximum tokens in generated responses
        """
        load_dotenv(override=True)
        self.model_name = model
        self.max_retries = max_retries

        self.max_concurrency = self._resolve_concurrency(max_concurrency, batch_size, default=0)
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}

        if not "temperature" in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        if verify_ssl is not True:
            # client_args are forwarded to the underlying httpx clients
            self.kwargs.setdefault("client_args", {"verify": self._ssl_verify(verify_ssl)})

        rate_limiter = self._make_rate_limiter(rpm)
        self.client = ChatGoogleGenerativeAI(model=model, rate_limiter=rate_limiter, **self.kwargs)
        self.client = self._add_retry_policy(self.client)
