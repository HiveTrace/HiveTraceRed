from typing import Optional, Union, Dict, Any
import os
import warnings

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from hivetracered.models.langchain_model import LangchainModel


class VLLMModel(LangchainModel):
    """
    vLLM model via LangChain.

    Connects to a vLLM server over the OpenAI-compatible API. Requires a running
    server, for example:
        vllm serve meta-llama/Llama-2-7b-chat-hf --api-key token-abc123

    The model parameter must match the model name the server was started with.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str,
        max_concurrency: Optional[int] = None,
        batch_size: Optional[int] = None,
        max_retries: int = 3,
        **kwargs,
    ):
        """
        Initialize the vLLM model client.

        Args:
            model: Model name on the vLLM server (e.g. meta-llama/Llama-2-7b-chat-hf).
            base_url: vLLM API URL (default: http://localhost:8000/v1).
            api_key: API key if the server was started with --api-key.
            max_concurrency: Maximum concurrent requests.
            batch_size: Deprecated. Use max_concurrency instead.
            max_retries: Number of retries on transient errors.
            **kwargs: Additional arguments for ChatOpenAI (temperature, max_tokens, etc.).
        """
        load_dotenv(override=True)

        self.model_name = model
        self.max_retries = max_retries

        if batch_size is not None:
            warnings.warn(
                "The 'batch_size' parameter is deprecated and will be removed in v2.0.0. "
                "Use 'max_concurrency' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if max_concurrency is None:
                max_concurrency = batch_size

        if max_concurrency is None:
            max_concurrency = 1
        self.max_concurrency = max_concurrency
        self.batch_size = self.max_concurrency

        base_url = base_url or os.getenv("VLLM_BASE_URL")
        api_key = api_key or os.getenv("VLLM_API_KEY")

        self.kwargs = kwargs or {}
        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        self.client = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            **self.kwargs,
        )
        self.client = self._add_retry_policy(self.client)
