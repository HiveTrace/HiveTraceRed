from typing import List, Any, Optional, Union, Dict
from abc import ABC, abstractmethod
import os
import aiohttp
import json
import asyncio
from hivetracered.models.base_model import Model
from dotenv import load_dotenv
import requests
from yandex_cloud_ml_sdk import YCloudML
from yandexcloud import SDK
from yandex_cloud_ml_sdk._retry import RetryPolicy
import warnings

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from yandex_cloud_ml_sdk._client import AioRpcError
from tqdm import tqdm
from typing import AsyncGenerator

class YandexGPTModel(Model):
    """
    Yandex GPT language model implementation with direct API integration.
    Provides access to Yandex's Russian language models with support for synchronous 
    and asynchronous operations, batched requests, and error handling.
    """
    
    def __init__(self, model="yandexgpt", max_concurrency: Optional[int] = None, batch_size: Optional[int] = None, max_retries: int = 3, **kwargs):
        """
        Initialize the Yandex GPT model client with the specified configuration.

        Args:
            model: Yandex model identifier (e.g., "yandexgpt", "yandexgpt-lite")
            max_concurrency: Maximum number of concurrent requests in batch operations (replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters for model configuration:
                     - temperature: Sampling temperature (lower = more deterministic)
                     - max_tokens: Maximum tokens in generated responses
                     - stream: Whether to stream the response
        """
        load_dotenv(override=True)
        self.model_name = model
        self.max_retries = max_retries

        # Handle deprecation
        if batch_size is not None:
            warnings.warn(
                "The 'batch_size' parameter is deprecated and will be removed in v2.0.0. "
                "Use 'max_concurrency' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            if max_concurrency is None:
                max_concurrency = batch_size

        # Set default if neither provided
        if max_concurrency is None:
            max_concurrency = 10

        self.max_concurrency = max_concurrency
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}

        if not "temperature" in self.kwargs:
            self.kwargs["temperature"] = 0.000001

        # Configure retry policy with exponential backoff and jitter
        retry_policy = RetryPolicy(
            max_attempts=self.max_retries,
        )

        sdk = YCloudML(
            folder_id=os.getenv("YANDEX_FOLDER_ID"),
            auth=os.getenv("YANDEX_GPT_API_KEY"),
            retry_policy=retry_policy,  # Pass retry policy to SDK
        )
        self.client = sdk.models.completions(self.model_name).configure(
            **self.kwargs
        )
        
    def _format_prompt(self, prompt: Union[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
        """
        Format the prompt for the Yandex GPT API.
        
        Args:
            prompt: Raw prompt as string or message list
            
        Returns:
            List of message dictionaries in Yandex API format
        """
        if isinstance(prompt, str):
            return [{"role": "user", "text": prompt}]
        else:
            # Convert LangChain message format to Yandex GPT format
            formatted_messages = []
            for message in prompt:
                role = message.get("role", "").lower()
                if role == "system":
                    formatted_messages.append({"role": "system", "text": message["content"]})
                elif role == "human" or role == "user":
                    formatted_messages.append({"role": "user", "text": message["content"]})
                elif role == "ai" or role == "assistant":
                    formatted_messages.append({"role": "assistant", "text": message["content"]})
            return formatted_messages
    
    def _format_response(self, response: Any) -> Dict:
        """
        Format the API response to match the expected output format.
        
        Args:
            response: Raw response from Yandex API
            
        Returns:
            Standardized response dictionary with content and metadata
        """
        alternative = response.alternatives[0]
        text = alternative.text
        role = alternative.role
        status = alternative.status
        tool_calls = alternative.tool_calls
        
        usage = {
            "input_text_tokens": response.usage.input_text_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "reasoning_tokens": response.usage.reasoning_tokens
        }
        model_version = response.model_version
        
        return {
            "content": text,
            "role": role,
            "status": status,
            "tool_calls": tool_calls,
            "usage": usage,
            "model_version": model_version
        }
    
    def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Send a single request to the model synchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with content and metadata
        """
        response = self.client.run(self._format_prompt(prompt))
        
        return self._format_response(response)
    
    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Send a single request to the model asynchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            Dictionary containing the model's response with content and metadata
            
        Note:
            Returns a fallback response if the API request fails
        """
        try:
            operation = self.client.run_deferred(self._format_prompt(prompt))
            response = operation.wait()
            return self._format_response(response)
        except AioRpcError as e:
            return {
                'content': 'В интернете есть много сайтов с информацией на эту тему. [Посмотрите, что нашлось в поиске](https://ya.ru)',
                'role': 'assistant',
                'status': 4
            }
    
    def batch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        """
        Send multiple requests to the model synchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
            
        Note:
            Uses ThreadPoolExecutor for concurrent processing when batch_size > 0
        """

        if self.max_concurrency == 0:
            results = []
            for prompt in tqdm(prompts, desc=f"Processing requests with {self.model_name}", unit="request"):
                results.append(self.invoke(prompt))
            return results
        else:
            with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
                futures = [executor.submit(self.invoke, prompt) for prompt in prompts]
                results = [future.result() for future in tqdm(futures, desc=f"Processing requests with {self.model_name}", unit="request")]
            return results

    async def abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        """
        Send multiple requests to the model asynchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            List of response dictionaries in the same order as the input prompts
            
        Note:
            Respects Yandex API rate limits (max 10 async requests per second)
        """
        operations = []
        formatted_prompts = [self._format_prompt(prompt) for prompt in prompts]
        last_operation = None
        
        # Yandex GPT API has a limit of 10 async requests per second
        for i in tqdm(range(0, len(formatted_prompts), self.max_concurrency),
                     desc=f"Submitting batches with {self.model_name}",
                     unit="batch"):
            for prompt in formatted_prompts[i:i + self.max_concurrency]:
                try:
                    operation = self.client.run_deferred(prompt)
                    last_operation = operation
                    operations.append(operation)
                except AioRpcError as e:
                    operations.append({
                        'content': 'В интернете есть много сайтов с информацией на эту тему. [Посмотрите, что нашлось в поиске](https://ya.ru)',
                        'role': 'assistant',
                        'status': 4
                    })
            time.sleep(1)

        # Wait for operations to complete
        if last_operation:
            with tqdm(total=1, desc=f"Waiting for operations to complete", unit="batch") as pbar:
                while last_operation.get_status().is_running:
                    time.sleep(0.1)
                pbar.update(1)

        # Collect results
        results = []
        for operation in operations:
            if isinstance(operation, dict):
                results.append(operation)
            else:
                results.append(self._format_response(operation.get_result()))
        return results
    
    def is_answer_blocked(self, answer: dict) -> bool:
        """
        Check if the answer is blocked by model's safety guardrails.
        
        Args:
            answer: The model response dictionary to check
            
        Returns:
            True if the response was blocked (status code 4), False otherwise
        """
        return answer["status"] == 4
    
    def get_params(self) -> dict:
        """
        Get the parameters of the model.
        
        Returns:
            Dictionary containing the model's configuration parameters
        """
        return {
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            **self.kwargs
        }

    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[dict, None]:
        """
        Send multiple requests to the model asynchronously and yield results as they complete.
        
        Args:
            prompts: A list of prompts to send to the model

        Yields:
            Response dictionaries as they become available
            
        Note:
            Processes each prompt individually for maximum responsiveness
        """
        operations = []
        
        formatted_prompts = [self._format_prompt(prompt) for prompt in prompts]
        # Yandex GPT API has a limit of 10 async requests per second
        batch_size = self.max_concurrency or len(formatted_prompts)
        for i in tqdm(range(0, len(formatted_prompts), batch_size),
                     desc=f"Submitting batches with {self.model_name}",
                     unit="batch"):
            for prompt in formatted_prompts[i:i + batch_size]:
                try:
                    operation = self.client.run_deferred(prompt)
                    operations.append(operation)
                except AioRpcError as e:
                    # Return error response with proper error metadata
                    operations.append({
                        'content': 'В интернете есть много сайтов с информацией на эту тему. [Посмотрите, что нашлось в поиске](https://ya.ru)',
                        'role': 'assistant',
                        'status': 4,
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
            time.sleep(1)

        # Use context manager for proper cleanup even if errors occur
        with tqdm(total=len(operations), desc=f"Processing requests with {self.model_name}", unit="request") as progress_bar:
            for operation in operations:
                progress_bar.update(1)

                if isinstance(operation, dict):
                    yield operation
                else:
                    response = operation.wait()
                    yield self._format_response(response)
