from typing import List, Any, Optional, Union, Dict
from langchain_gigachat import GigaChat
from models.langchain_model import LangchainModel
import os
from dotenv import load_dotenv

class GigaChatModel(LangchainModel):
    """
    GigaChat language model implementation using LangChain integration.
    Provides standardized access to Sber's GigaChat models with support for
    both synchronous and asynchronous request processing.
    """
    
    def __init__(self, model: str = "GigaChat", batch_size: int = 1, scope: str = os.getenv("GIGACHAT_API_SCOPE"), credentials: str=os.getenv("GIGACHAT_CREDENTIALS"), verify_ssl_certs: bool = False, **kwargs):
        """
        Initialize the GigaChat model client with the specified configuration.
        
        Args:
            model: GigaChat model variant (e.g., "GigaChat", "GigaChat-Pro")
            batch_size: Number of requests to process in parallel
            scope: API scope for authorization (from env or explicit)
            credentials: API credentials for authentication (from env or explicit)
            verify_ssl_certs: Whether to verify SSL certificates for API connections
            **kwargs: Additional parameters for model configuration:
                     - profanity_check: Whether to enable profanity filtering
                     - temperature: Sampling temperature (lower = more deterministic)
                     - max_tokens: Maximum tokens in generated responses
                     - top_p: Top-p sampling parameter for response diversity
        """
        load_dotenv(override=True)
        self.model_name = model
        self.kwargs = kwargs or {}
        if not "temperature" in self.kwargs:
            self.kwargs["temperature"] = 0.000001
        self.client = GigaChat(credentials=credentials, model=model, scope=scope, verify_ssl_certs=verify_ssl_certs, **self.kwargs)
        self.batch_size = batch_size

    