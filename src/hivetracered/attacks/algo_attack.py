from typing import Union, List, Dict, Optional
from collections.abc import AsyncGenerator
from abc import ABC, abstractmethod
from hivetracered.attacks.template_attack import TemplateAttack

class AlgoAttack(TemplateAttack, ABC):
    """
    Abstract base class for algorithmic attacks that apply transformations to text.
    Provides options to apply transformations with or without instructions, giving flexibility
    to deliver raw transformations or transformations wrapped in template instructions.
    """
    
    def __init__(self, raw: bool = False, template: str | None = None, name: str | None = None, description: str | None = None):
        """
        Initialize the algorithmic attack.
        
        Args:
            raw: If True, applies the transformation without instructions; if False, wraps with template
            template: Custom instruction template with '{prompt}' placeholder; uses default if None
            name: Optional name for the attack (defaults to class name)
            description: Optional description for the attack
        """
        super().__init__(template=template, name=name, description=description)
        self.raw = raw
    
    @abstractmethod
    def transform(self, text: str, **kwargs) -> str:
        """
        Apply the algorithmic transformation to the input text.
        
        Args:
            text: The input text to transform
            **kwargs: Additional parameters specific to the transformation
            
        Returns:
            The transformed text
        """
        pass
    
    def apply(self, prompt: str | list[dict[str, str]]) -> str | list[dict[str, str]]:
        """
        Apply the attack to the given prompt, with or without instructions based on the raw flag.
        
        Args:
            prompt: A string or list of messages to apply the attack to
            
        Returns:
            The transformed prompt with the attack applied
        """
        if isinstance(prompt, str):
            transformed_text = self.transform(prompt)
            
            if self.raw:
                return transformed_text
            else:
                instruction_prompt = self.template.format(prompt=transformed_text)
                return instruction_prompt
        
        else:  # For list of messages format
            result = prompt.copy()
            for i in range(len(result) - 1, -1, -1):
                if result[i].get("role") == "user":
                    content = result[i].get("content", "")
                    transformed_text = self.transform(content)
                    
                    if self.raw:
                        result[i]["content"] = transformed_text
                    else:
                        instruction_prompt = self.template.format(prompt=transformed_text)
                        result[i]["content"] = instruction_prompt
            
            return result
        
    async def stream_abatch(self, prompts: list[str | list[dict[str, str]]]) -> AsyncGenerator[list[str | list[dict[str, str]]], None]:
        """
        Apply the attack to a batch of prompts asynchronously.
        
        Args:
            prompts: A list of prompts to apply the attack to
            
        Returns:
            An async generator yielding transformed prompts
        """
        for prompt in prompts:
            yield self.apply(prompt)

    def _get_mode(self, raw: bool = False) -> str:
        """
        Get the mode of the attack.
        
        Args:
            raw: Whether the mode is raw or templated
            
        Returns:
            String indicating the attack mode
        """
        return " Raw" if raw else ""
