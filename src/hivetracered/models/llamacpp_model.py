from typing import List, Any, Optional, Union, Dict
from langchain_community.chat_models import ChatLlamaCpp
from hivetracered.models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os
from typing import AsyncGenerator
import asyncio
from tqdm import tqdm
import multiprocessing

class LlamaCppModel(LangchainModel):
    """
    Llama.cpp local model implementation using the LangChain integration.
    Provides a standardized interface to locally-hosted GGUF models via llama-cpp-python,
    supporting both synchronous and asynchronous processing capabilities.

    This model enables running quantized LLMs locally without external APIs or services,
    providing privacy, cost savings, and no rate limits. Supports GPU acceleration
    through CUDA, Metal, or other backends.
    """

    def __init__(
        self,
        model_path: str,
        batch_size: int = 5,
        n_ctx: int = 10000,
        n_gpu_layers: int = -1,
        n_batch: int = 512,
        n_threads: Optional[int] = None,
        max_retries: int = 3,
        **kwargs
    ):
        """
        Initialize the Llama.cpp model client with the specified configuration.

        Args:
            model_path: Path to the GGUF model file (e.g., "/path/to/model.gguf")
                       Required parameter - must point to a valid GGUF format model
            batch_size: Number of requests to process in parallel (default: 5)
                       Local models can typically handle 1-10 depending on hardware
            n_ctx: Context window size in tokens (default: 10000)
                  Should match or be less than the model's trained context length
            n_gpu_layers: Number of layers to offload to GPU (default: -1 for auto-detection)
                         Set to 0 for CPU-only, or specify exact number (e.g., 32)
                         Requires llama-cpp-python built with GPU support (CUDA/Metal/etc)
            n_batch: Batch size for prompt processing (default: 512)
                    Higher values use more memory but may be faster
            n_threads: Number of CPU threads to use (default: None for auto-detect)
                      If None, uses cpu_count - 1 to leave one thread for system
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters to pass to the ChatLlamaCpp constructor:
                     - temperature: Sampling temperature (default: 0.7, lower = more deterministic)
                     - top_p: Top-p sampling parameter (nucleus sampling)
                     - top_k: Top-k sampling parameter
                     - repeat_penalty: Penalty for repeated tokens (default: 1.1)
                     - max_tokens: Maximum tokens to generate (default: 512)
                     - verbose: Enable verbose logging (default: False)


        Note:
            Requires llama-cpp-python to be installed:

            CPU-only:
                pip install llama-cpp-python

            NVIDIA GPU (CUDA):
                CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python

            Apple Silicon (Metal):
                CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python

            Download GGUF models from Hugging Face:
                https://huggingface.co/models?library=gguf
        """
        load_dotenv(override=True)
        self.model_name = f"llamacpp:{os.path.basename(model_path)}"
        self.max_retries = max_retries

        # Validate model path
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                f"Please provide a valid path to a GGUF model file."
            )

        self.kwargs = kwargs or {}

        # Set default temperature if not provided
        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        # Auto-detect CPU threads if not specified
        if n_threads is None:
            n_threads = max(1, multiprocessing.cpu_count() - 1)

        self.batch_size = batch_size
        self.client = ChatLlamaCpp(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_threads=n_threads,
            **self.kwargs
        )
        self.client = self._add_retry_policy(self.client)
