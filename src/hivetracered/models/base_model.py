from typing import List, Any, Optional, Union, Dict
from collections.abc import AsyncGenerator
from abc import ABC, abstractmethod

class Model(ABC):
    """
    Abstract base class for language model implementations.
    Defines the standard interface for interacting with various LLM providers,
    supporting both synchronous and asynchronous operations for single requests and batches.
    """
    model_name: str

    @abstractmethod
    def invoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model synchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with at least a 'content' key
        """
        pass
    
    @abstractmethod
    async def ainvoke(self, prompt: str | list[dict[str, str]]) -> dict:
        """
        Send a single request to the model asynchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with at least a 'content' key
        """
        pass
    
    @abstractmethod
    def batch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model synchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
        """
        pass
    
    @abstractmethod
    async def abatch(self, prompts: list[str | list[dict[str, str]]]) -> list[dict]:
        """
        Send multiple requests to the model asynchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
        """
        pass
    
    def is_answer_blocked(self, answer: dict) -> bool:
        """
        Check if the answer is blocked by model's safety guardrails.
        
        Args:
            answer: The model response dictionary to check
            
        Returns:
            Boolean indicating if the response was blocked
        """
        return False
    
    def get_params(self) -> dict:
        """
        Get the parameters of the model.
        
        Returns:
            Dictionary containing the model's configuration parameters
        """
        return self.__dict__
    
    @abstractmethod
    async def stream_abatch(self, prompts: list[str | list[dict[str, str]]]) -> AsyncGenerator[dict, None]:
        """
        Send multiple requests to the model asynchronously and yield results as they complete.
        
        Args:
            prompts: A list of prompts to send to the model

        Yields:
            Response dictionaries. Implementations MUST yield results in the same order
            as the input prompts list, since downstream stages match responses to prompts
            by sequential index.
        """
        pass

