from typing import Union, List, Any, Dict, AsyncGenerator
from abc import ABC, abstractmethod

class BaseAttack(ABC):
    """
    Abstract base class for all attack implementations.
    Defines the standard interface for applying attacks to prompts in both synchronous and asynchronous contexts.
    """
    
    @abstractmethod
    def apply(self, prompt: Union[str, List[Dict[str, str]]]) -> Union[str, List[Dict[str, str]]]:
        """
        Apply the attack to the given prompt.
        
        Args:
            prompt: A string or list of messages to apply the attack to
            
        Returns:
            The transformed prompt with the attack applied
        """
        pass
    
    @abstractmethod
    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[List[Union[str, List[Dict[str, str]]]], None]:
        """
        Apply the attack asynchronously to a batch of prompts.
        
        Args:
            prompts: A list of prompts to apply the attack to
            
        Returns:
            An async generator yielding transformed prompts as they are processed
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the attack.
        
        Returns:
            The name of the attack
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Get the description of the attack.
        
        Returns:
            A description of what the attack does
        """
        pass

    def get_params(self):
        """
        Get the parameters of the attack.
        
        Returns:
            A dictionary containing the attack's parameters
        """
        return self.__dict__

    def __or__(self, other):
        """
        Allows using the | operator to compose attacks: attack1 | attack2 means attack1(attack2(prompt)).
        
        Args:
            other: Another BaseAttack instance to compose with this one
            
        Returns:
            A ComposedAttack instance that applies attacks in sequence
        """
        from hivetracered.attacks.composed_attack import ComposedAttack
        if not isinstance(other, BaseAttack):
            return NotImplemented
        return ComposedAttack(outer_attack=self, inner_attack=other)