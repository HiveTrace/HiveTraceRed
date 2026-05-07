from langchain_openai import ChatOpenAI
from hivetracered.models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os

from hivetracered.registry import Registry

@Registry.model()
class OpenAIModel(LangchainModel):
    """
    OpenAI-compatible language model implementation using the LangChain integration.
    Provides a standardized interface to OpenAI's API (or any OpenAI-compatible endpoint)
    with rate limiting support and both synchronous and asynchronous processing capabilities.
    """

    def __init__(self, model: str = "gpt-4.1-nano", base_url: str = "https://api.openai.com/v1", max_concurrency: int | None = None, batch_size: int | None = None, rpm: int = 300, api_key: str | None = None, max_retries: int = 3, **kwargs):
        """
        Initialize the OpenAI model client with the specified configuration.

        Args:
            model: Model identifier (e.g., "gpt-4", "gpt-3.5-turbo", or any model name for compatible APIs)
            base_url: API base URL (default: "https://api.openai.com/v1"). Override for OpenAI-compatible endpoints.
            max_concurrency: Maximum number of concurrent requests (replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            rpm: Rate limit in requests per minute
            api_key: API key; defaults to OPENAI_API_KEY env var
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters to pass to the ChatOpenAI constructor
        """
        load_dotenv(override=True)

        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        self.base_url = base_url
        self.model_name = model
        self.max_retries = max_retries

        self.max_concurrency = self._resolve_concurrency(max_concurrency, batch_size, default=1)
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}

        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001
        rate_limiter = self._make_rate_limiter(rpm)
        self.client = ChatOpenAI(model=model, rate_limiter=rate_limiter, base_url=base_url, api_key=api_key, **self.kwargs)
        self.client = self._add_retry_policy(self.client)
