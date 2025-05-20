from typing import List, Any, Optional, Union, Dict
from langchain_openai import ChatOpenAI
from models.langchain_model import LangchainModel
from dotenv import load_dotenv
import os
from typing import AsyncGenerator
import asyncio
from tqdm import tqdm

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import RunnableLambda

class OpenAIModel(LangchainModel):
    """
    OpenAI language model implementation using the LangChain integration.
    Provides a standardized interface to OpenAI's API with rate limiting support and 
    both synchronous and asynchronous processing capabilities.
    """
    
    def __init__(self, model: str = "gpt-4.1-nano", batch_size: int = 1, rpm: int = 300, **kwargs):
        """
        Initialize the OpenAI model client with the specified configuration.
        
        Args:
            model: OpenAI model identifier (e.g., "gpt-4", "gpt-3.5-turbo")
            batch_size: Number of requests to process in parallel
            rpm: Rate limit in requests per minute
            **kwargs: Additional parameters to pass to the ChatOpenAI constructor
        """
        load_dotenv(override=True)
        self.model_name = model
        
        self.kwargs = kwargs or {}
        
        if not "temperature" in self.kwargs:
            self.kwargs["temperature"] = 0.000001
        
        self.batch_size = batch_size
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=rpm / 60,
            check_every_n_seconds=0.1,
        )
        self.client = ChatOpenAI(model=model, rate_limiter=rate_limiter, **self.kwargs)
    