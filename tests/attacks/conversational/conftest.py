"""Shared test doubles for conversational attack tests.

Provides MockEvaluator, RefusalOnFirstCallEvaluator, and model helpers used
across tests/attacks/conversational/test_crescendo_attack.py.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from hivetracered.evaluators.base_evaluator import BaseEvaluator
from tests.conftest import MockModel


class MockEvaluator(BaseEvaluator):
    """Controllable evaluator that returns queued verdicts then a default.

    Pass ``results`` to pre-load ordered return values; once exhausted,
    ``default`` is returned on every subsequent call.
    """

    def __init__(
        self,
        results: Optional[List[Dict[str, Any]]] = None,
        default: Optional[Dict[str, Any]] = None,
    ):
        self.results = list(results or [])
        self.default = default or {"success": False}
        self.calls: List[tuple] = []

    def _next(self) -> Dict[str, Any]:
        if self.results:
            return self.results.pop(0)
        return dict(self.default)

    def evaluate(self, prompt, response):
        self.calls.append((prompt, response))
        return self._next()

    async def stream_abatch(self, prompts, responses) -> AsyncGenerator[Dict[str, Any], None]:
        for prompt, response in zip(prompts, responses):
            self.calls.append((prompt, response))
            yield self._next()

    def get_name(self) -> str:
        return "MockEvaluator"

    def get_description(self) -> str:
        return "test double"

    def get_params(self) -> Dict[str, Any]:
        return {}


class RefusalOnFirstCallEvaluator(MockEvaluator):
    """Evaluator that refuses on first call only; accepts on subsequent calls.

    Used by SPEC-013 to simulate refusal_cap exhaustion in iteration 0
    and normal acceptance in iteration 1 — without inline class definitions
    or if-branching inside the test body.

    Polarity note: this fixture follows the standard evaluator contract used
    throughout the framework — ``success=True`` means the response is
    compliant/harmful (i.e. *not* a refusal); ``success=False`` means the
    response is a refusal. Crescendo's refusal_judge interprets these
    accordingly (``refused = not success``).
    """

    def __init__(self):
        super().__init__()
        self._call_count = 0

    def evaluate(self, prompt, response):
        self._call_count += 1
        if self._call_count == 1:
            return {"success": False}  # refuse (standard contract: not-success ⇔ refusal)
        return {"success": True}       # accept (standard contract: success ⇔ compliant)

    async def stream_abatch(self, prompts, responses):
        for p, r in zip(prompts, responses):
            yield self.evaluate(p, r)


class FailOnFirstCallModel(MockModel):
    """MockModel that raises RuntimeError on the first invoke() call, then succeeds.

    Used by SPEC-017 and SPEC-023 to simulate transient attacker failures
    without inline class definitions or if-branching inside test bodies.
    """

    def __init__(self, response=None, exc=None):
        super().__init__(response=response)
        self._exc = exc or RuntimeError("first-call failure")
        self._invoke_count = 0

    def invoke(self, prompt, **kwargs):
        self._invoke_count += 1
        if self._invoke_count == 1:
            raise self._exc
        return self._get_response(prompt)

    async def ainvoke(self, prompt, **kwargs):
        return self.invoke(prompt, **kwargs)


class FailOnFirstCallTargetModel(MockModel):
    """MockModel that raises KeyError('content') on first invoke(); succeeds after.

    Used by SPEC-018 to simulate transient target failures without
    inline class definitions or if-branching inside test bodies.
    """

    def __init__(self, response=None):
        super().__init__(response=response)
        self._invoke_count = 0

    def invoke(self, prompt, **kwargs):
        self._invoke_count += 1
        if self._invoke_count == 1:
            raise KeyError("content")
        return self._get_response(prompt)

    async def ainvoke(self, prompt, **kwargs):
        return self.invoke(prompt, **kwargs)


class FailOnFirstCallEvaluator(MockEvaluator):
    """Evaluator that raises RuntimeError on the first evaluate() call, then accepts.

    Used by SPEC-019 to simulate transient refusal-judge failures without
    inline class definitions or if-branching inside test bodies. Under the
    standard contract ``success=True`` means compliant/not-refused, so the
    post-failure return commits the turn.
    """

    def __init__(self):
        super().__init__()
        self._call_count = 0

    def evaluate(self, prompt, response):
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("judge error")
        return {"success": True}  # accept (standard contract: success ⇔ compliant)

    async def stream_abatch(self, prompts, responses):
        for p, r in zip(prompts, responses):
            yield self.evaluate(p, r)


class AlwaysRaisingEvaluator(MockEvaluator):
    """Evaluator that always raises RuntimeError on evaluate().

    Used by SPEC-020 to simulate a completely broken success judge without
    inline class definitions inside test bodies.
    """

    def evaluate(self, prompt, response):
        raise RuntimeError("judge error")

    async def stream_abatch(self, prompts, responses):
        for p, r in zip(prompts, responses):
            yield self.evaluate(p, r)


class AlwaysRaisingModel(MockModel):
    """MockModel that always raises RuntimeError on invoke() / ainvoke().

    Used by SPEC-023 to simulate total attacker failure.
    """

    def invoke(self, prompt, **kwargs):
        raise RuntimeError("always fails")

    async def ainvoke(self, prompt, **kwargs):
        raise RuntimeError("always fails")


class PlainTextThenValidModel(MockModel):
    """MockModel that returns plain text on first invoke(), valid JSON on second.

    Used by SPEC-030 to simulate a malformed attacker response (missing q field)
    without inline class definitions or if-branching in the test body.
    """

    _VALID_ATK_JSON = '{"q": "question", "summary": "summary"}'

    def __init__(self, response=None):
        super().__init__(response=response)
        self._invoke_count = 0

    def invoke(self, prompt, **kwargs):
        self._invoke_count += 1
        if self._invoke_count == 1:
            return {"content": "sorry I cannot help"}
        return {"content": self._VALID_ATK_JSON}

    async def ainvoke(self, prompt, **kwargs):
        return self.invoke(prompt, **kwargs)


