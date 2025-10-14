from typing import Union, List, Optional, Dict, AsyncGenerator
from hivetracered.attacks.base_attack import BaseAttack

class TemplateAttack(BaseAttack):
    """
    A base class for template-based attacks.
    Allows creating new attacks by defining a template string with a '{prompt}' placeholder where the original prompt will be inserted.
    """
    
    def __init__(self, template: str = "{prompt}", name: Optional[str] = None, description: Optional[str] = None):
        """
        Initialize the template attack with a specific template string.
        
        Args:
            template: A format string with a '{prompt}' placeholder
            name: Optional name for the attack (defaults to class name)
            description: Optional description for the attack
        """
        self.template = template
        self._name = name
        self._description = description
    
    def apply(self, prompt: Union[str, List[Dict[str, str]]]) -> Union[str, List[Dict[str, str]]]:
        """
        Apply the template attack to the given prompt.
        
        Args:
            prompt: A string or list of messages to apply the attack to. 
                   If the prompt is a list, the template will be applied to the last message.
                   
        Returns:
            The transformed prompt with the template applied
            
        Raises:
            ValueError: If the prompt is invalid or the last message is not a human message
        """
        if isinstance(prompt, str):
            return self.template.format(prompt=prompt)
        
        elif isinstance(prompt, list):
            transformed_messages = prompt[:-1]

            if prompt[-1].get("role") == "human":
                transformed_messages.append({"role": "human", "content": self.template.format(prompt=prompt[-1]["content"])})
            else:
                raise ValueError("Last message in prompt is not a human message")

            return transformed_messages
        else:
            raise ValueError("Prompt is not a string or list of messages")
    
    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[List[Union[str, List[Dict[str, str]]]], None]:
        """
        Apply the template attack to a batch of prompts asynchronously.
        
        Args:
            prompts: A list of prompts to apply the attack to
            
        Returns:
            An async generator yielding transformed prompts
        """
        for prompt in prompts:
            yield self.apply(prompt)
    
    def get_name(self) -> str:
        """
        Get the name of the attack.
        
        Returns:
            The custom name if provided, otherwise the class name
        """
        if self._name:
            return self._name
        return self.__class__.__name__
    
    def get_description(self) -> str:
        """
        Get the description of the attack.
        
        Returns:
            The custom description if provided, otherwise a default description based on the template
        """
        if self._description:
            return self._description
        return f"Template attack using template: {self.template}" 
    
    def get_params(self):
        """
        Get the parameters of the attack.
        
        Returns:
            A dictionary containing the attack's parameters
        """
        return {
            "template": self.template,
            "name": self.get_name(),
            "description": self.get_description()
        }
