from typing import Union, List, Dict, Optional, AsyncGenerator
from hivetracered.attacks.base_attack import BaseAttack

class ComposedAttack(BaseAttack):
    """
    An attack that composes two attacks sequentially, where the output of the inner attack 
    becomes the input to the outer attack, creating a pipeline of transformations.
    """
    def __init__(self, outer_attack: BaseAttack, inner_attack: BaseAttack, name: Optional[str] = None, description: Optional[str] = None):
        """
        Initialize a composed attack with inner and outer attack components.
        
        Args:
            outer_attack: The attack to apply second in the composition
            inner_attack: The attack to apply first in the composition
            name: Optional custom name for the attack (defaults to "Composed(outer ∘ inner)")
            description: Optional custom description (defaults to composition description)
        """
        self.outer_attack = outer_attack
        self.inner_attack = inner_attack
        self._name = name or f"Composed({outer_attack.get_name()} ∘ {inner_attack.get_name()})"
        self._description = description or f"Composes {outer_attack.get_name()} after {inner_attack.get_name()}"

    def apply(self, prompt: Union[str, List[Dict[str, str]]]) -> Union[str, List[Dict[str, str]]]:
        """
        Apply the inner attack followed by the outer attack to the given prompt.
        
        Args:
            prompt: A string or list of messages to apply the attacks to
            
        Returns:
            The transformed prompt with both attacks applied sequentially
        """
        inner_result = self.inner_attack.apply(prompt)
        return self.outer_attack.apply(inner_result)

    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[List[Union[str, List[Dict[str, str]]]], None]:
        """
        Apply the composition of attacks to a batch of prompts asynchronously.
        
        Args:
            prompts: A list of prompts to apply the attacks to
            
        Returns:
            An async generator yielding transformed prompts
        """
        # First, apply inner attack to all prompts
        inner_results = []
        async for result in self.inner_attack.stream_abatch(prompts):
            inner_results.append(result)
        # Then, apply outer attack to all results
        async for result in self.outer_attack.stream_abatch(inner_results):
            yield result

    def get_name(self) -> str:
        """
        Get the name of the attack.
        
        Returns:
            The custom name if provided, otherwise a generated name based on component attacks
        """
        return self._name

    def get_description(self) -> str:
        """
        Get the description of the attack.
        
        Returns:
            The custom description if provided, otherwise a generated description
        """
        return self._description

    def get_params(self):
        """
        Get the parameters of the attack.
        
        Returns:
            A dictionary containing both the inner and outer attack parameters
        """
        return {
            "outer_attack": self.outer_attack.get_params(),
            "inner_attack": self.inner_attack.get_params(),
            "name": self.get_name(),
            "description": self.get_description(),
        } 