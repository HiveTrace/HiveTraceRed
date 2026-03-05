"""
Generic REST model for interacting with arbitrary HTTP endpoints.

Connects to any REST endpoint by specifying a URI, request body template
with ``$INPUT`` / ``$KEY`` placeholders, response extraction path, headers, and auth.

Use cases: Testing models behind custom API gateways, internal endpoints,
model-serving platforms (e.g., vLLM, TGI, Triton), or any service with a REST API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp
import requests
from dotenv import load_dotenv
from tqdm import tqdm

from hivetracered.models.base_model import Model

import jsonpath_ng
from jsonpath_ng.exceptions import JsonPathParserError

try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class RestModel(Model):
    """
    Generic REST API model with configurable request/response templates.

    Connects to any REST endpoint by specifying a URI, request body template
    with ``$INPUT`` placeholder, response extraction path, headers, and auth.

    Example::

        model = RestModel(
            uri="http://localhost:8080/v1/chat/completions",
            model="my-model",
            headers={"Authorization": "Bearer sk-xxx", "Content-Type": "application/json"},
            req_template={
                "model": "my-model",
                "messages": [{"role": "user", "content": "$INPUT"}],
            },
            response_json_field="$.choices[0].message.content",
        )
        result = model.invoke("Hello!")
        # {"content": "Hi there!"}
    """

    def __init__(
        self,
        uri: str,
        model: str = "rest",
        *,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        req_template: Optional[Dict[str, Any]] = None,
        response_json_field: Optional[str] = None,
        api_key: Optional[str] = None,
        request_timeout: int = 20,
        verify_ssl: bool = True,
        ratelimit_codes: Optional[List[int]] = [429],
        skip_codes: Optional[List[int]] = [],
        retry_5xx: bool = True,
        max_retries: int = 3,
        max_concurrency: Optional[int] = None,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        load_dotenv(override=True)
        self.model_name = model
        self.uri = uri
        self.method = method.upper()
        self.headers = headers or {"Content-Type": "application/json"}
        self.req_template = req_template
        self.response_json_field = response_json_field
        self.request_timeout = request_timeout
        self.verify_ssl = verify_ssl
        self.ratelimit_codes = ratelimit_codes
        self.skip_codes = skip_codes
        self.retry_5xx = retry_5xx
        self.max_retries = max_retries
        self.proxies = proxies
        self.kwargs = kwargs

        self.max_concurrency = max_concurrency or 10

        self._api_key = api_key or ""

        # Validate and pre-compile JSONPath expression
        self._jsonpath_expr = None
        if self.response_json_field:
            try:
                self._jsonpath_expr = jsonpath_ng.parse(self.response_json_field)
            except JsonPathParserError as e:
                logger.critical(
                    "Couldn't parse response_json_field %s", self.response_json_field
                )
                raise e

    # ── placeholder helpers ──────────────────────────────────────────

    def _substitute_in_obj(self, obj: Any, prompt: str, key: str) -> Any:
        if isinstance(obj, str):
            return obj.replace("$INPUT", prompt).replace("$KEY", key)
        if isinstance(obj, dict):
            return {k: self._substitute_in_obj(v, prompt, key) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._substitute_in_obj(item, prompt, key) for item in obj]
        return obj

    # ── prompt extraction ────────────────────────────────────────────

    @staticmethod
    def _extract_prompt_text(prompt: Union[str, List[Dict[str, str]]]) -> str:
        if isinstance(prompt, str):
            return prompt
        parts = []
        for msg in prompt:
            role = msg.get("role", "")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}" if role else content)
        return "\n".join(parts)

    # ── request / response ───────────────────────────────────────────

    def _build_request(self, prompt_text: str) -> tuple:
        """Return (url, headers, body_bytes_or_None)."""
        key = self._api_key
        url = self._substitute_in_obj(self.uri, prompt_text, key)
        hdrs = {k: self._substitute_in_obj(v, prompt_text, key) for k, v in self.headers.items()}

        body = None
        if self.req_template is not None:
            body = json.dumps(
                self._substitute_in_obj(self.req_template, prompt_text, key),
                ensure_ascii=False,
            ).encode("utf-8")

        return url, hdrs, body

    def _parse_response(self, status_code: int, text: str) -> dict:
        if not self.response_json_field or not text or not text.strip():
            return {"content": text or ""}

        data = json.loads(text)

        matches = self._jsonpath_expr.find(data)
        if matches:
            return {"content": str(matches[0].value)}
        raise ValueError(
            f"JSONPath '{self.response_json_field}' matched nothing in response"
        )

    def _should_retry(self, status_code: int) -> bool:
        if status_code in self.ratelimit_codes:
            return True
        if self.retry_5xx and 500 <= status_code < 600:
            return True
        return False

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        """Exponential backoff with full jitter."""
        base = min(2 ** attempt, 60)
        return random.uniform(0, base)

    def _get_aiohttp_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies.get("https") or self.proxies.get("http")

    # ── sync invoke ──────────────────────────────────────────────────

    def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        prompt_text = self._extract_prompt_text(prompt)
        url, hdrs, body = self._build_request(prompt_text)

        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.request(
                    self.method,
                    url,
                    headers=hdrs,
                    data=body,
                    timeout=self.request_timeout,
                    verify=self.verify_ssl,
                    proxies=self.proxies,
                )

                if resp.status_code in self.skip_codes:
                    return {"content": ""}

                if self._should_retry(resp.status_code) and attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt))
                    continue

                resp.raise_for_status()
                return self._parse_response(resp.status_code, resp.text)
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt))
                    continue
                logger.exception("RestModel.invoke failed")
                return {
                    "content": "",
                    "error": str(e),
                    "error_type": type(e).__name__,
                }

    # ── async invoke ─────────────────────────────────────────────────

    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> dict:
        prompt_text = self._extract_prompt_text(prompt)
        url, hdrs, body = self._build_request(prompt_text)

        for attempt in range(self.max_retries + 1):
            try:
                connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
                timeout = aiohttp.ClientTimeout(total=self.request_timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.request(
                        self.method,
                        url,
                        headers=hdrs,
                        data=body,
                        proxy=self._get_aiohttp_proxy(),
                    ) as resp:
                        text = await resp.text()

                        if resp.status in self.skip_codes:
                            return {"content": ""}

                        if self._should_retry(resp.status) and attempt < self.max_retries:
                            await asyncio.sleep(self._retry_delay(attempt))
                            continue

                        if resp.status >= 400:
                            raise aiohttp.ClientResponseError(
                                resp.request_info,
                                resp.history,
                                status=resp.status,
                                message=text,
                            )
                        return self._parse_response(resp.status, text)
            except Exception as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                logger.exception("RestModel.ainvoke failed")
                return {
                    "content": "",
                    "error": str(e),
                    "error_type": type(e).__name__,
                }

    # ── batch (sync, threaded) ───────────────────────────────────────

    def batch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        if self.max_concurrency == 0:
            results = []
            for prompt in tqdm(prompts, desc=f"Processing requests with {self.model_name}", unit="request"):
                results.append(self.invoke(prompt))
            return results

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = [executor.submit(self.invoke, prompt) for prompt in prompts]
            results = [
                future.result()
                for future in tqdm(futures, desc=f"Processing requests with {self.model_name}", unit="request")
            ]
        return results

    # ── abatch (async, semaphore) ────────────────────────────────────

    async def abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> List[dict]:
        semaphore = asyncio.Semaphore(self.max_concurrency or len(prompts))

        async def sem_task(idx, prompt):
            async with semaphore:
                result = await self.ainvoke(prompt)
                return idx, result

        tasks = [asyncio.create_task(sem_task(i, p)) for i, p in enumerate(prompts)]
        ordered = [None] * len(prompts)

        with tqdm(total=len(tasks), desc=f"Processing requests with {self.model_name}", unit="request") as pbar:
            for coro in asyncio.as_completed(tasks):
                idx, result = await coro
                ordered[idx] = result
                pbar.update(1)

        return ordered

    # ── stream_abatch ────────────────────────────────────────────────

    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]]) -> AsyncGenerator[dict, None]:
        semaphore = asyncio.Semaphore(self.max_concurrency or len(prompts))

        async def sem_task(idx, prompt):
            async with semaphore:
                try:
                    result = await self.ainvoke(prompt)
                    return idx, result, None
                except Exception as e:
                    return idx, {"content": "", "error": str(e), "error_type": type(e).__name__}, e

        tasks = [asyncio.create_task(sem_task(i, p)) for i, p in enumerate(prompts)]

        results = {}
        cur_result_idx = 0

        with tqdm(total=len(tasks), desc=f"Processing requests with {self.model_name}", unit="request") as progress_bar:
            for task in asyncio.as_completed(tasks):
                idx, res, error = await task
                progress_bar.update(1)

                results[idx] = res
                while cur_result_idx in results:
                    yield results.pop(cur_result_idx)
                    cur_result_idx += 1

    def get_params(self) -> dict:
        return {
            "model_name": self.model_name,
            "uri": self.uri,
            "method": self.method,
            "headers": {k: ("***" if "key" in k.lower() or "auth" in k.lower() else v) for k, v in self.headers.items()},
            "response_json_field": self.response_json_field,
            "max_concurrency": self.max_concurrency,
            "max_retries": self.max_retries,
            "request_timeout": self.request_timeout,
            "retry_5xx": self.retry_5xx,
            "skip_codes": self.skip_codes,
            "verify_ssl": self.verify_ssl,
            **self.kwargs,
        }
