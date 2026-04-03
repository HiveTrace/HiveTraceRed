"""Shared test fixtures and mock objects for HiveTraceRed test suite."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import pytest

from hivetracered.models.base_model import Model


class MockModel(Model):
    """Mock model for testing attacks and evaluators without real API calls.

    Args:
        response: Default response dict returned by invoke/ainvoke.
        side_effect: If callable, called with (prompt) to produce response.
                     If list, responses are popped in order.
    """

    model_name: str = "mock"

    def __init__(
        self,
        response: Optional[Dict[str, Any]] = None,
        side_effect: Optional[Any] = None,
    ):
        self.default_response = response or {"content": "mock response"}
        self.side_effect = side_effect
        self.call_log: List[Any] = []

    def _get_response(self, prompt: Any) -> dict:
        self.call_log.append(prompt)
        if self.side_effect is not None:
            if callable(self.side_effect):
                return self.side_effect(prompt)
            if isinstance(self.side_effect, list) and self.side_effect:
                return self.side_effect.pop(0)
        return self.default_response.copy()

    def invoke(self, prompt: Union[str, List[Dict[str, str]]], **kwargs) -> dict:
        return self._get_response(prompt)

    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]], **kwargs) -> dict:
        return self._get_response(prompt)

    def batch(self, prompts: List[Union[str, List[Dict[str, str]]]], **kwargs) -> List[dict]:
        return [self._get_response(p) for p in prompts]

    async def abatch(self, prompts: List[Union[str, List[Dict[str, str]]]], **kwargs) -> List[dict]:
        return [self._get_response(p) for p in prompts]

    async def stream_abatch(self, prompts: List[Union[str, List[Dict[str, str]]]], **kwargs) -> AsyncGenerator[dict, None]:
        for p in prompts:
            yield self._get_response(p)

    def get_params(self) -> dict:
        return {"model_name": self.model_name}


# ── Async helpers ────────────────────────────────────────────────────


async def _async_collect(async_gen: AsyncGenerator) -> list:
    """Collect all items from an async generator into a list."""
    results = []
    async for item in async_gen:
        results.append(item)
    return results


def async_collect(async_gen: AsyncGenerator) -> list:
    """Synchronous wrapper: collect all items from an async generator."""
    return asyncio.get_event_loop().run_until_complete(_async_collect(async_gen))


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_model():
    """Fresh MockModel with default response."""
    return MockModel()


@pytest.fixture
def sample_string_prompt():
    return "Tell me something"


@pytest.fixture
def sample_message_prompt_human():
    """Message list with role='human' (used by TemplateAttack, ModelAttack)."""
    return [{"role": "human", "content": "Tell me something"}]


@pytest.fixture
def sample_message_prompt_user():
    """Message list with role='user' (used by AlgoAttack)."""
    return [{"role": "user", "content": "Tell me something"}]


@pytest.fixture
def sample_message_prompt_with_system():
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "human", "content": "Tell me something"},
    ]
