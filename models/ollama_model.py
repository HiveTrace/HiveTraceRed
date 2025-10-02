from typing import List, Any, Optional, Union, Dict
from langchain_ollama import ChatOllama
from models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os
from typing import AsyncGenerator
import asyncio
from tqdm import tqdm

class OllamaModel(LangchainModel):
    """
    Ollama local model implementation using the LangChain integration.
    Provides a standardized interface to locally-hosted open-source models via Ollama,
    supporting both synchronous and asynchronous processing capabilities.

    Ollama allows running models like Llama, Mistral, Qwen, and others locally
    without relying on cloud APIs, providing privacy, cost savings, and no rate limits.
    """

    def __init__(
        self,
        model: str = "ollama/qwen3:0.6b",
        batch_size: int = 5,
        base_url: str = "http://localhost:11434",
        max_retries: int = 3,
        **kwargs
    ):
        """
        Initialize the Ollama model client with the specified configuration.

        Args:
            model: Ollama model identifier (e.g., "llama3.2", "mistral", "qwen2.5:72b")
                   Use `ollama list` to see available models on your system
            batch_size: Number of requests to process in parallel (local models can handle 5-20
                       depending on hardware; 0 for unlimited)
            base_url: URL of the Ollama server (default: "http://localhost:11434")
                     Can be set to remote Ollama server if running elsewhere
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters to pass to the ChatOllama constructor:
                     - temperature: Sampling temperature (lower = more deterministic)
                     - top_p: Top-p sampling parameter
                     - top_k: Top-k sampling parameter
                     - num_predict: Maximum tokens to generate
                     - repeat_penalty: Penalty for repeated tokens
                     - stop: List of stop sequences

        Note:
            Requires Ollama to be installed and running. Download from https://ollama.com

            Pull models with: `ollama pull ollama/qwen3:0.6b`
            Start server with: `ollama serve` (usually runs automatically)
        """
        load_dotenv(override=True)
        self.model_name = model
        self.max_retries = max_retries

        # Allow override from environment variable
        base_url = os.getenv("OLLAMA_BASE_URL", base_url)

        self.kwargs = kwargs or {}

        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        self.batch_size = batch_size
        self.client = ChatOllama(
            model=model,
            base_url=base_url,
            **self.kwargs
        )
        self.client = self._add_retry_policy(self.client)
