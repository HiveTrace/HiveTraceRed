from typing import Any
from collections.abc import AsyncGenerator
from abc import ABC, abstractmethod

class BaseEvaluator(ABC):
    """
    Abstract base class for all evaluators that assess model responses.
    Defines the standard interface for evaluating models' outputs for security vulnerabilities.
    """
    
    @abstractmethod
    def evaluate(self, prompt: str | list[dict[str, str]], response: Any) -> dict[str, Any]:
        """
        Evaluate a model response to a given prompt.
        
        Args:
            prompt: The original prompt as a string or list of messages
            response: The model's response to evaluate
            
        Returns:
            A dictionary containing evaluation results and metrics
        """
        pass
    
    @abstractmethod
    async def stream_abatch(self, prompts: list[dict[str, str]], responses: list[Any]) -> AsyncGenerator[dict[str, Any], None]:
        """
        Asynchronously evaluate multiple prompts and responses.
        
        Args:
            prompts: List of prompts that elicited responses
            responses: List of model responses to evaluate
            
        Yields:
            Evaluation result dictionaries for each prompt-response pair
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the evaluator.
        
        Returns:
            The unique identifier name of the evaluator
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Get the description of the evaluator.
        
        Returns:
            A description of the evaluator's purpose and methodology
        """
        pass 
    
    @abstractmethod
    def get_params(self) -> dict[str, Any]:
        """
        Get the parameters of the evaluator.
        
        Returns:
            Dictionary of evaluator configuration parameters
        """
        pass