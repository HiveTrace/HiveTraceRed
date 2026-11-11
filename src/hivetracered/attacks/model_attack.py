from typing import Any
from collections.abc import AsyncGenerator
from contextlib import aclosing
from hivetracered.attacks.base_attack import AttackModelError, BaseAttack
from hivetracered.models.structured_output import OutputRequest, object_format
from hivetracered.models.base_model import Model

def _output_template(template, instruction, prefix):
    return template.replace('{output_instruction}', instruction).replace('{output_prefix}', prefix)


class ModelAttack(BaseAttack):
    """
    Attack that uses a language model to transform prompts based on an attacker prompt template.
    Leverages the model's abilities to generate adversarial prompts through prompt engineering.
    """
    
    def __init__(self, 
                 model: Model,
                 attacker_prompt: str, 
                 model_kwargs: dict[str, Any] | None = None,
                 name: str | None = None, 
                 description: str | None = None,
                 structured_output: bool = True,
                 output_instruction: str = '',
                 output_prefix: str = '',
                 structured_output_instruction: str = ''):
        """
        Initialize the model attack with a specific model and attacker prompt.
        
        Args:
            model: The language model to use for the attack
            attacker_prompt: The prompt template to use for the attack, with {prompt} as placeholder
            model_kwargs: Optional additional arguments to pass to the model
            name: Optional name for the attack (defaults to class name)
            description: Optional description for the attack
        """
        self.structured_output = structured_output
        self.model = model
        self.attacker_prompt = _output_template(attacker_prompt, output_instruction, output_prefix)
        self.structured_attacker_prompt = _output_template(attacker_prompt, structured_output_instruction, '')
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

        return response
    
    def _output_request(self):
        format_ = object_format({'prompt': {'type': 'string', 'description': 'The requested result text, without an introductory label, response prefix, or explanation.'}}) if self.structured_output else None
        return OutputRequest(self.model, format_, **self.model_kwargs)

    def _format_prompt(self, prompt, native=False):
        if isinstance(prompt, str):
            text = prompt
        elif isinstance(prompt, list) and prompt and prompt[-1].get('role') == 'human':
            text = prompt[-1]['content']
        else:
            raise ValueError('Prompt must be a string or a list with the last message from human')
        template = self.structured_attacker_prompt if native else self.attacker_prompt
        result = template.format(prompt=text)
        if native:
            result += '\nReturn only JSON matching the response schema. Put only the requested result in "prompt", without an introductory label, response prefix, or explanation.'
        return result

    def _restore_prompt(self, prompt, content):
        return content if isinstance(prompt, str) else prompt[:-1] + [{'role': 'human', 'content': content}]

    def _decode(self, response, native):
        response = self._output_request().checked(response, native, ('prompt',))
        if response.get('error'):
            raise AttackModelError(response['error'])
        content = response['structured_output']['prompt'] if native else response.get('content', '')
        return content if native else self.post_process_response(content)

    def apply(self, prompt):
        if not isinstance(prompt, (str, list)):
            raise ValueError('Prompt is not a string or list of messages')
        if isinstance(prompt, list) and (not prompt or prompt[-1].get('role') != 'human'):
            raise ValueError('Last message in prompt is not a human message')
        ordinary = self._format_prompt(prompt)
        response, native = self._output_request().invoke(
            self._format_prompt(prompt, native=True), ordinary)
        return self._restore_prompt(prompt, self._decode(response, native))

    async def batch(self, prompts):
        return [value async for value in self.stream_abatch(prompts)]

    async def stream_abatch(self, prompts):
        ordinary = [self._format_prompt(prompt) for prompt in prompts]
        structured = [self._format_prompt(prompt, native=True) for prompt in prompts]
        async with aclosing(self._output_request().stream(structured, ordinary)) as responses:
            index = 0
            async for response, native in responses:
                try:
                    yield self._restore_prompt(prompts[index], self._decode(response, native))
                except AttackModelError as exc:
                    yield self._restore_prompt(prompts[index], ''), {'attack_error': exc.error}
                index += 1

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