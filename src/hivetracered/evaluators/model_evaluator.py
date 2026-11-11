import re
from contextlib import aclosing
from hivetracered.models.structured_output import OutputRequest, object_format, parse_object
from typing import Any
from collections.abc import AsyncGenerator
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.models.base_model import Model
from abc import abstractmethod
class ModelEvaluator(BaseEvaluator):
    """
    Evaluator that uses a language model to evaluate prompts and responses.
    This class can be extended to implement specific evaluation methodologies.
    """
    
    OUTPUT_FIELDS = {}

    def __init__(self, 
                 model: Model,
                 evaluation_prompt_template: str,
                 name: str | None = None,
                 description: str | None = None,
                 structured_output: bool = True):
        """
        Initialize the model-based evaluator.
        
        Args:
            model: The model to use for evaluation
            evaluation_prompt_template: Template string for formatting the evaluation prompt
            name: Optional name for the evaluator
            description: Optional description for the evaluator
        """
        self.structured_output = structured_output
        self.model = model
        self.evaluation_prompt_template = evaluation_prompt_template
        self._name = name
        self._description = description
    
    def _get_extra_format_kwargs(self) -> dict[str, Any]:
        """
        Return extra keyword arguments for the evaluation prompt template.

        Override in subclasses to inject additional placeholders (e.g. {goal}).
        """
        return {}

    def create_evaluation_prompt(self, prompt: str | list[dict[str, str]], response: Any) -> str:
        """
        Create the evaluation prompt to send to the model.

        Args:
            prompt: The original prompt as a string or list of messages
            response: The model's response to evaluate. Accepts a string,
                a dict with a ``content`` key, an object exposing a
                ``.content`` attribute (e.g. LangChain message), or any
                value with a sensible ``__str__``.

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
            response=response_text,
            **self._get_extra_format_kwargs(),
        )
    
    def evaluate(self, prompt: str | list[dict[str, str]], response: str) -> dict[str, Any]:
        """
        Evaluate a model response by using another model as evaluator.
        
        Args:
            prompt: The original prompt as a string or list of messages
            response: The model's response to evaluate
            
        Returns:
            A dictionary containing evaluation results
        """
        evaluation_prompt = self.create_evaluation_prompt(prompt, response)
        evaluation_response, native = self._output_request().invoke(
            evaluation_prompt + '\nReturn only JSON matching the response schema.', evaluation_prompt)
        return self._checked_evaluation(evaluation_response, native)
    
    
    @abstractmethod
    def _parse_evaluation_response(self, evaluation_response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse the evaluation response from the model.
        """
        pass

    def _extract_answer(self, text: str, pattern: str, default: str) -> str:
        """
        Extract an answer using a regex pattern.

        Args:
            text: The text to search in
            pattern: The regex pattern to use
            default: The default value to return if no match is found

        Returns:
            The extracted answer or the default value
        """
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.group(1):
            return match.group(1).lower()
        return default
    
    async def stream_abatch(self, prompts: list[dict[str, str]], responses: list[Any]) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream a batch of evaluations.
        """
        evaluation_prompts = [self.create_evaluation_prompt(prompt, response) for prompt, response in zip(prompts, responses)]
        
        structured = [prompt + '\nReturn only JSON matching the response schema.' for prompt in evaluation_prompts]
        async with aclosing(self._output_request().stream(structured, evaluation_prompts)) as stream:
            async for evaluation_response, native in stream:
                yield self._checked_evaluation(evaluation_response, native)

    def _output_request(self):
        format_ = object_format(self.OUTPUT_FIELDS) if self.structured_output and self.OUTPUT_FIELDS else None
        return OutputRequest(self.model, format_)

    def _checked_evaluation(self, response: dict, native) -> dict:
        if response.get("error"):
            return {"success": False, "evaluation_error": response["error"], "raw_evaluation": response}
        try:
            parsed = response
            if native:
                data = parse_object(response, self._output_request().format)
                parsed = {**response, 'structured_output': data}
            result = self._parse_evaluation_response(parsed)
            if native:
                result['raw_evaluation'] = response
            if any(str(result.get(k, "")).lower() in ("error", "ошибка")
                   for k in (self.OUTPUT_FIELDS or ("is_harmful", "did_answer", "should_answer", "should_block"))):
                result["evaluation_error"] = "Invalid judge verdict"
            return result
        except Exception as exc:
            return {"success": False, "evaluation_error": str(exc), "raw_evaluation": response}

    def get_name(self) -> str:
        return self._name or 'Model-based Evaluator'

    def get_description(self) -> str:
        return self._description or 'Evaluates responses using a language model to analyze prompt-response pairs'

    def get_params(self) -> dict[str, Any]:
        """
        Get the parameters of the evaluator.
        """
        return {
            **self.model.get_params(),
            "evaluation_prompt_template": self.evaluation_prompt_template,
            "structured_output": self.structured_output,
            "name": self.get_name(),
            "description": self.get_description(),
        }


class ChoiceEvaluator(ModelEvaluator):
    PLAIN_FORMAT = 'numbered'
    ERROR_VALUE = 'ошибка'
    SUCCESS_WHEN = {}
    ANY_SUCCESS = {}
    DEFAULT_NAME = 'Model-based Evaluator'
    DEFAULT_DESCRIPTION = 'Evaluates prompt-response pairs'
    PROMPT_TEMPLATE = ''

    def __init__(self, model, name=None, description=None, structured_output: bool = True):
        super().__init__(model, self.PROMPT_TEMPLATE,
                         name or self.DEFAULT_NAME, description or self.DEFAULT_DESCRIPTION, structured_output)

    def _json_answers(self, content):
        import json
        start, end = content.find('{'), content.rfind('}')
        try:
            data = json.loads(content[start:end + 1])
            return {key: str(data.get(key, self.ERROR_VALUE)).strip().lower() for key in self.OUTPUT_FIELDS}
        except (ValueError, TypeError, AttributeError):
            return dict.fromkeys(self.OUTPUT_FIELDS, self.ERROR_VALUE)

    def _numbered_answers(self, content):
        if self.PLAIN_FORMAT == 'regex' or content.strip().startswith('1'):
            return {key: self._extract_answer(content, rf"{index}\.\s*({'|'.join(map(re.escape, field['enum']))})", self.ERROR_VALUE)
                    for index, (key, field) in enumerate(self.OUTPUT_FIELDS.items(), 1)}
        values = [re.sub(r'^\d+\.\s*', '', value.strip()) for value in content.strip().split('\n')]
        if len(values) != len(self.OUTPUT_FIELDS):
            return dict.fromkeys(self.OUTPUT_FIELDS, self.ERROR_VALUE)
        return dict(zip(self.OUTPUT_FIELDS, values))

    def _answers(self, response):
        if 'structured_output' in response:
            return response['structured_output']
        content = response['content'].lower()
        return self._json_answers(content) if self.PLAIN_FORMAT == 'json' else self._numbered_answers(content)

    def _parse_evaluation_response(self, evaluation_response):
        answers = self._answers(evaluation_response)
        success = all(answers[key] == value for key, value in self.SUCCESS_WHEN.items())
        success = success and (not self.ANY_SUCCESS or any(answers[key] == value for key, value in self.ANY_SUCCESS.items()))
        return {**answers, 'success': success, 'raw_evaluation': evaluation_response}
