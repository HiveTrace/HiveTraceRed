from typing import Dict, Any, Union, List, Optional, AsyncGenerator
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.models.base_model import Model
from abc import abstractmethod
class ModelEvaluator(BaseEvaluator):
    """
    Evaluator that uses a language model to evaluate prompts and responses.
    This class can be extended to implement specific evaluation methodologies.
    """
    
    def __init__(self, 
                 model: Model,
                 evaluation_prompt_template: str,
                 name: Optional[str] = None,
                 description: Optional[str] = None):
        """
        Initialize the model-based evaluator.
        
        Args:
            model: The model to use for evaluation
            evaluation_prompt_template: Template string for formatting the evaluation prompt
            name: Optional name for the evaluator
            description: Optional description for the evaluator
        """
        self.model = model
        self.evaluation_prompt_template = evaluation_prompt_template
        self._name = name
        self._description = description
    
    def create_evaluation_prompt(self, prompt: Union[str, List[Dict[str, str]]], response: str) -> str:
        """
        Create the evaluation prompt to send to the model.
        
        Args:
            prompt: The original prompt as a string or list of messages
            response: The model's response to evaluate
            
        Returns:
            The formatted evaluation prompt
        """
        # Extract the prompt text
        if isinstance(prompt, str):
            prompt_text = prompt
        elif isinstance(prompt, list) and all(isinstance(item, dict) for item in prompt):
            # For chat-style prompts, concatenate all roles and content
            prompt_text = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in prompt if "content" in msg])
        else:
            prompt_text = str(prompt)
        
        # Extract the response text
        if hasattr(response, 'content'):
            response_text = response.content
        elif isinstance(response, str):
            response_text = response
        elif isinstance(response, dict) and "content" in response:
            response_text = response["content"]
        else:
            response_text = str(response)
        
        # Format the evaluation prompt
        return self.evaluation_prompt_template.format(
            prompt=prompt_text,
            response=response_text
        )
    
    def evaluate(self, prompt: Union[str, List[Dict[str, str]]], response: str) -> Dict[str, Any]:
        """
        Evaluate a model response by using another model as evaluator.
        
        Args:
            prompt: The original prompt as a string or list of messages
            response: The model's response to evaluate
            
        Returns:
            A dictionary containing evaluation results
        """
        evaluation_prompt = self.create_evaluation_prompt(prompt, response)
        evaluation_response = self.model.invoke(evaluation_prompt)
        return self._parse_evaluation_response(evaluation_response)
    
    
    @abstractmethod
    def _parse_evaluation_response(self, evaluation_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the evaluation response from the model.
        """
        pass
    
    async def stream_abatch(self, prompts: List[Dict[str, str]], responses: List[Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a batch of evaluations.
        """
        evaluation_prompts = [self.create_evaluation_prompt(prompt, response) for prompt, response in zip(prompts, responses)]
        
        async for evaluation_response in self.model.stream_abatch(evaluation_prompts):
            yield self._parse_evaluation_response(evaluation_response)

    def get_name(self) -> str:
        """
        Get the name of the evaluator.
        
        Returns:
            The name of the evaluator
        """
        if self._name:
            return self._name
        
        return "Model-based Evaluator"
    
    def get_description(self) -> str:
        """
        Get the description of the evaluator.
        
        Returns:
            A description of what the evaluator does
        """
        if self._description:
            return self._description
        
        return "Evaluates responses using a language model to analyze prompt-response pairs" 
    
    def get_params(self) -> Dict[str, Any]:
        """
        Get the parameters of the evaluator.
        """
        return {
            **self.model.get_params(),
            "evaluation_prompt_template": self.evaluation_prompt_template,
            "name": self.get_name(),
            "description": self.get_description(),
        }
