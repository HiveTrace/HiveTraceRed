from typing import List, Any, Optional, Union, Dict, AsyncGenerator
from hivetracered.models.base_model import Model
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import asyncio
from tqdm import tqdm
import time
import json
import warnings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    RetryError,
)



class GeminiNativeModel(Model):
    """
    Google Gemini language model implementation using Google's native Generative AI SDK.
    Provides direct access to Gemini's advanced features including structured outputs,
    thinking budget, and rate limiting with both synchronous and asynchronous interfaces.
    """
    
    def __init__(self, model: str = "gemini-2.5-flash-preview-04-17", max_concurrency: Optional[int] = None, batch_size: Optional[int] = None, thinking_budget: int = 0, rpm: int = 10, max_retries: int = 3, **kwargs):
        """
        Initialize the Gemini model with the specified configuration.

        Args:
            model: Gemini model identifier (e.g., "gemini-2.5-flash", "gemini-1.5-pro")
            max_concurrency: Maximum number of concurrent requests (0 for unlimited, replaces batch_size)
            batch_size: (Deprecated) Use max_concurrency instead. Will be removed in v2.0.0
            thinking_budget: Number of tokens allocated for model thinking/reasoning steps
            rpm: Rate limit in requests per minute (0 for unlimited)
            max_retries: Maximum number of retry attempts on transient errors (default: 3)
            **kwargs: Additional parameters for model configuration:
                     - temperature: Sampling temperature (lower = more deterministic)
                     - top_p, top_k: Sampling parameters for controlling response diversity
                     - max_output_tokens: Maximum tokens in generated responses
        """
        load_dotenv(override=True)
        self.model_name = model
        self.thinking_budget = thinking_budget
        self.rpm = rpm
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
            max_concurrency = 0

        self.max_concurrency = max_concurrency
        # Keep for backward compatibility in get_params()
        self.batch_size = self.max_concurrency

        self.kwargs = kwargs or {}
        self.config = types.GenerateContentConfig(
            temperature=self.kwargs.get("temperature", 0.000001),
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget),
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string"
                    }
                }
            }
        )
        
        # Rate limiting variables
        self.last_request_time = 0
        self.request_times = []
        self._rate_limit_lock = asyncio.Lock()
        
        # Set a very low temperature if not specified
        if "temperature" not in self.kwargs:
            self.kwargs["temperature"] = 0.000001
        
        # Initialize the Google Generative AI client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        self.client = genai.Client()

    def _create_retry_decorator(self):
        """
        Create a retry decorator configured for this model's max_retries setting.

        Retries on:
        - Connection errors (network failures)
        - Timeout errors
        - Server errors (500, 503)
        - Rate limit errors (429)

        Uses exponential backoff with jitter to prevent thundering herd.

        Returns:
            Configured tenacity retry decorator
        """
        return retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            retry=retry_if_exception_type((
                ConnectionError,
                TimeoutError,
                # Add more specific exceptions as needed
                Exception,
            )),
            reraise=True,
        )

    def _wait_for_rate_limit(self):
        """
        Wait synchronously if necessary to comply with the RPM limit.
        
        Implements a sliding window approach for rate limiting based on
        requests made in the last 60 seconds.
        """
        if self.rpm <= 0:
            return
            
        current_time = time.time()
        
        # Clean up old request times (older than 60 seconds)
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # If we've hit the RPM limit, wait until we can make another request
        if len(self.request_times) >= self.rpm:
            # Calculate how long to wait
            oldest_request = min(self.request_times)
            wait_time = 60 - (current_time - oldest_request)
            if wait_time > 0:
                time.sleep(wait_time)
        
        # Record this request
        self.request_times.append(time.time())
    
    async def _await_rate_limit(self):
        """
        Wait asynchronously if necessary to comply with the RPM limit.
        
        Uses an async lock to ensure thread-safe access to the request times list
        and implements a sliding window approach for rate limiting.
        """
        if self.rpm <= 0:
            return
            
        async with self._rate_limit_lock:
            current_time = time.time()
            
            # Clean up old request times (older than 60 seconds)
            self.request_times = [t for t in self.request_times if current_time - t < 60]
            
            # If we've hit the RPM limit, wait until we can make another request
            if len(self.request_times) >= self.rpm:
                # Calculate how long to wait
                oldest_request = min(self.request_times)
                wait_time = 60 - (current_time - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # Record this request
            self.request_times.append(time.time())
    
    def _parse_structured_response(self, response):
        """
        Parse the structured JSON response from the model.
        
        Args:
            response: The raw response from the Gemini model
            
        Returns:
            Dictionary containing the parsed response with both text content
            and structured content (if successfully parsed as JSON)
        """
        parsed_content = response.text
        structured_content = None
        
        try:
            structured_content = json.loads(parsed_content)
            parsed_content = structured_content["response"]
        except Exception as e:
            # If parsing fails, fall back to text response
            print(f"Warning: Failed to parse structured response: {str(e)}")
        
        return {
            "content": parsed_content,
            "structured_content": structured_content,
            "raw_response": response
        }
    
    def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Send a single request to the model synchronously with automatic retries.

        Args:
            prompt: A string or list of messages to send to the model

        Returns:
            Dictionary containing the model's response with content, structured content (if applicable),
            and metadata including model name and any error information
        """
        # Create retry decorator and wrap the internal call
        retry_decorator = self._create_retry_decorator()
        try:
            return retry_decorator(self._invoke_internal)(prompt)
        except Exception as e:
            # After all retries exhausted, return error response
            return {
                "content": f"Error: {str(e)}",
                "model": self.model_name,
                "error": str(e)
            }

    def _invoke_internal(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Internal method that performs the actual API call (wrapped by retry logic).
        Raises exceptions for retry logic to handle.
        """
        # Apply rate limiting
        self._wait_for_rate_limit()

        # Handle different prompt formats
        if isinstance(prompt, str):
            content = prompt
        elif isinstance(prompt, list):
            # Convert message format to Gemini format
            content = []
            for message in prompt:
                role = message.get("role", "user")
                # Adjust role names to match Gemini's expectations
                if role == "assistant":
                    role = "model"
                if role == "system":
                    role = "user"

                content.append({
                    "role": role,
                    "parts": [{"text": message.get("content", "")}]
                })
        else:
            raise ValueError("Prompt must be a string or a list of messages")

        # Let exceptions propagate for retry logic to catch
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=content,
            config=self.config,
            **{k: v for k, v in self.kwargs.items() if k not in ["temperature", "thinking_budget", "rpm"]}
        )

        # Parse the structured response
        parsed_response = self._parse_structured_response(response)

        return {
            "content": parsed_response["content"],
            "structured_content": parsed_response["structured_content"],
            "model": self.model_name,
            "role": "assistant",
            "raw_response": response
        }
    
    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        """
        Send a single request to the model asynchronously.
        
        Args:
            prompt: A string or list of messages to send to the model
            
        Returns:
            The model's response
        """
        
        # Since the Google API doesn't have a native async interface,
        # we'll run the synchronous method in an executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.invoke, prompt)
    
    def batch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        """
        Send multiple requests to the model synchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            A list of model responses
        """
        results = []

        batch_size = self.max_concurrency or len(prompts)

        for i in tqdm(range(0, len(prompts), batch_size), desc=f"Processing with {self.model_name}"):
            batch_prompts = prompts[i:i+batch_size]
            batch_results = []
            
            for prompt in batch_prompts:
                result = self.invoke(prompt)
                batch_results.append(result)
            
            results.extend(batch_results)
        
        return results
    
    async def abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        """
        Send multiple requests to the model asynchronously.
        
        Args:
            prompts: A list of prompts to send to the model
            
        Returns:
            A list of model responses
        """
        results = []

        batch_size = self.max_concurrency or len(prompts)

        for i in range(0, len(prompts), batch_size):
            batch_prompts = prompts[i:i+batch_size]
            tasks = [self.ainvoke(prompt) for prompt in batch_prompts]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        
        return results 
        
    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[dict, None]:
        """
        Send multiple requests to the model asynchronously and yield results as they complete.

        Args:
            prompts: A list of prompts to send to the model

        Returns:
            An async generator of model responses in order of completion
        """

        batch_size = self.max_concurrency or len(prompts)

        async def safe_ainvoke(prompt):
            """Wrapper that catches exceptions and returns error response."""
            try:
                return await self.ainvoke(prompt)
            except Exception as e:
                # Return error response instead of crashing entire batch
                return {
                    "content": "",
                    "error": str(e),
                    "error_type": type(e).__name__
                }

        # Track all pending tasks
        pending_tasks = set()

        # Create initial batch of tasks
        next_prompt_index = 0

        # Add tasks up to the batch_size or available prompts
        while len(pending_tasks) < batch_size and next_prompt_index < len(prompts):
            task = asyncio.create_task(safe_ainvoke(prompts[next_prompt_index]))
            pending_tasks.add(task)
            next_prompt_index += 1

        # Use context manager for proper cleanup even if errors occur
        with tqdm(total=len(prompts), desc=f"Processing requests with {self.model_name}", unit="request") as progress_bar:
            # Process tasks and add new ones as they complete
            while pending_tasks:
                # Wait for the first task to complete
                done, pending = await asyncio.wait(
                    pending_tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Update pending tasks
                pending_tasks = pending

                # Process completed tasks
                for task in done:
                    result = await task
                    progress_bar.update(1)
                    yield result

                    # Add a new task if there are more prompts
                    if next_prompt_index < len(prompts):
                        new_task = asyncio.create_task(safe_ainvoke(prompts[next_prompt_index]))
                        pending_tasks.add(new_task)
                        next_prompt_index += 1 

    def get_params(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "batch_size": self.batch_size,
            "thinking_budget": self.thinking_budget,
            "rpm": self.rpm,
            "temperature": self.kwargs.get("temperature", 0.000001)
        }