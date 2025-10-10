from typing import Union, List, Optional, Dict, Any, AsyncGenerator
from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.models.base_model import Model

class ModelAttack(BaseAttack):
    """
    Attack that uses a language model to transform prompts based on an attacker prompt template.
    Leverages the model's abilities to generate adversarial prompts through prompt engineering.
    """
    
    def __init__(self, 
                 model: Model,
                 attacker_prompt: str, 
                 model_kwargs: Optional[Dict[str, Any]] = None,
                 name: Optional[str] = None, 
                 description: Optional[str] = None):
        """
        Initialize the model attack with a specific model and attacker prompt.
        
        Args:
            model: The language model to use for the attack
            attacker_prompt: The prompt template to use for the attack, with {prompt} as placeholder
            model_kwargs: Optional additional arguments to pass to the model
            name: Optional name for the attack (defaults to class name)
            description: Optional description for the attack
        """
        self.model = model
        self.attacker_prompt = attacker_prompt
        self.model_kwargs = model_kwargs or {}
        self._name = name
        self._description = description
    
    def post_process_response(self, response: str) -> str:
        """
        Post-process the model's response to clean it and handle refusals.
        
        Args:
            response: The raw response from the model
            
        Returns:
            The cleaned and processed response
        """

        pref_suffixes = [
            "** ",
            "**\n",
            "**\n",
            "\n\n",
            "\n",
            " ",
        ]
        prefixes_to_remove = [
            "преобразованный промпт:", 
            "исходное намерение:",
            "вредоносное намерение:",
        ]
        
        for prefix in prefixes_to_remove:
            for pref in pref_suffixes:
                lower_response = response.lower()
                if prefix + pref in lower_response:
                    index = lower_response.index(prefix + pref)
                    response = response[index + len(prefix + pref):].lstrip()
        
        # Check for refusal patterns and attempt to extract usable content
        refusal_indicators = [
            "я не могу"
        ]
        
        # If the entire response is a refusal, try to extract any useful content that follows
        if any(indicator in response.lower() for indicator in refusal_indicators):
            response = "Я не могу ответить на этот вопрос"
        
        return response
    
    def apply(self, prompt: Union[str, List[Dict[str, str]]]) -> Union[str, List[Dict[str, str]]]:
        """
        Apply the model attack to the given prompt.
        
        Args:
            prompt: A string or list of messages to apply the attack to
            
        Returns:
            The transformed prompt with the model attack applied
            
        Raises:
            ValueError: If the prompt format is invalid
        """
        if isinstance(prompt, str):
            # Format the attacker prompt with the user prompt
            formatted_prompt = self.attacker_prompt.format(prompt=prompt)
            # Get the model's response
            response = self.model.invoke(formatted_prompt, **self.model_kwargs)["content"]
            # Post-process the response
            response = self.post_process_response(response)
            return response
        
        elif isinstance(prompt, list):
            transformed_messages = prompt[:-1]

            if prompt[-1].get("role") == "human":
                # Format the attacker prompt with the last message content
                formatted_prompt = self.attacker_prompt.format(prompt=prompt[-1]["content"])
                # Get the model's response
                response = self.model.invoke(formatted_prompt, **self.model_kwargs)["content"]
                # Post-process the response
                response = self.post_process_response(response)
                transformed_messages.append({"role": "human", "content": response})
            else:
                raise ValueError("Last message in prompt is not a human message")

            return transformed_messages
        else:
            raise ValueError("Prompt is not a string or list of messages")
    
    async def batch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[Union[str, List[Dict[str, str]]]]:
        """
        Apply the model attack to a batch of prompts in a non-streaming manner.
        
        Args:
            prompts: A list of prompts to apply the attack to
            
        Returns:
            List of transformed prompts with the model attack applied
            
        Raises:
            ValueError: If any prompt has an invalid format
        """
        formatted_prompts = []
        
        # Process each prompt according to its role and format with attacker prompt
        for prompt in prompts:
            if isinstance(prompt, str):
                # Format the attacker prompt with the user prompt
                formatted_prompts.append(self.attacker_prompt.format(prompt=prompt))
            elif isinstance(prompt, list) and prompt and prompt[-1].get("role") == "human":
                # Format the attacker prompt with the last message content
                formatted_prompts.append(self.attacker_prompt.format(prompt=prompt[-1]["content"]))
            else:
                raise ValueError("Prompt must be either a string or a list with the last message from human")
        
        # Use the model's abatch method to process all prompts at once
        responses = await self.model.abatch(formatted_prompts)
        
        # Format the responses back according to their original type
        transformed_prompts = []
        for i, prompt in enumerate(prompts):
            if isinstance(prompt, str):
                # For string prompts, return the model response content with post-processing
                transformed_prompts.append(self.post_process_response(responses[i]["content"]))
            elif isinstance(prompt, list):
                # For list prompts, keep all messages except the last and append the transformed message
                transformed_messages = prompt[:-1]
                # Post-process the response
                processed_response = self.post_process_response(responses[i]["content"])
                transformed_messages.append({"role": "human", "content": processed_response})
                transformed_prompts.append(transformed_messages)
        
        return transformed_prompts
    
    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[List[Union[str, List[Dict[str, str]]]], None]:
        """
        Apply the model attack to a batch of prompts asynchronously.
        
        Args:
            prompts: A list of prompts to apply the attack to
            
        Returns:
            An async generator yielding transformed prompts as they are processed
            
        Raises:
            ValueError: If any prompt has an invalid format
        """
        formatted_prompts = []
        
        # Process each prompt according to its role and format with attacker prompt
        for prompt in prompts:
            if isinstance(prompt, str):
                # Format the attacker prompt with the user prompt
                formatted_prompts.append(self.attacker_prompt.format(prompt=prompt))
            elif isinstance(prompt, list) and prompt and prompt[-1].get("role") == "human":
                # Format the attacker prompt with the last message content
                formatted_prompts.append(self.attacker_prompt.format(prompt=prompt[-1]["content"]))
            else:
                raise ValueError("Prompt must be either a string or a list with the last message from human")
        
        i = 0
        async for response in self.model.stream_abatch(formatted_prompts):
            if isinstance(prompts[i], str):
                # For string prompts, return the model response content with post-processing
                yield self.post_process_response(response["content"])
            elif isinstance(prompts[i], list):
                # For list prompts, keep all messages except the last and append the transformed message
                transformed_messages = prompts[i][:-1]
                # Post-process the response
                processed_response = self.post_process_response(response["content"])
                transformed_messages.append({"role": "human", "content": processed_response})
                yield transformed_messages
            i += 1
            
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
            The custom description if provided, otherwise a default description
        """
        if self._description:
            return self._description
        return f"Model-based attack using {self.model.__class__.__name__} with prompt: {self.attacker_prompt}" 