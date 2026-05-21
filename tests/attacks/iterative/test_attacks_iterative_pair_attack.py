"""Unit tests for hivetracered.attacks.types.single_turn.iterative.pair_attack.PAIRAttack.

Covers PAIR-specific behavior: linear iterative refinement, success-stop,
max_iterations cap, best-attack tracking, language-config switching,
sync + async parity, and the JSON extraction fallback when the attacker
model emits an unparseable response.

Mocking discipline: only architectural seams are mocked (attacker model, target
model, evaluator). The PAIRAttack class itself is never patched.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest

from hivetracered.attacks.iterative_attack import (
    ENGLISH_LANGUAGE_CONFIG,
    RUSSIAN_LANGUAGE_CONFIG,
    IterativeAttackResult,
    LanguageConfig,
)
from hivetracered.attacks.types.single_turn.iterative.pair_attack import (
    DEFAULT_ATTACKER_SYSTEM_PROMPT,
    PAIRAttack,
)
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from tests.conftest import MockModel


# ── Test doubles ────────────────────────────────────────────────────


class _MockEvaluator(BaseEvaluator):
    """Controllable evaluator that returns a queue of (score, success) results."""

    def __init__(
        self,
        results: Optional[List[Dict[str, Any]]] = None,
        default: Optional[Dict[str, Any]] = None,
    ):
        self.results = list(results or [])
        self.default = default or {"success": False, "score": 0.0}
        self.calls: List[tuple] = []

    def _next(self) -> Dict[str, Any]:
        if self.results:
            return self.results.pop(0)
        return dict(self.default)

    def evaluate(self, prompt, response):
        self.calls.append((prompt, response))
        return self._next()

    async def stream_abatch(
        self, prompts: List, responses: List
    ) -> AsyncGenerator[Dict[str, Any], None]:
        for prompt, response in zip(prompts, responses):
            self.calls.append((prompt, response))
            yield self._next()

    def get_name(self) -> str:
        return "MockEvaluator"

    def get_description(self) -> str:
        return "test double"

    def get_params(self) -> Dict[str, Any]:
        return {}


def _atk_json(prompt_text: str, improvement: str = "x") -> Dict[str, Any]:
    """Build a MockModel content dict with valid attacker JSON."""
    return {
        "content": json.dumps({"improvement": improvement, "prompt": prompt_text})
    }


def _make_attack(
    *,
    attacker: Optional[MockModel] = None,
    target: Optional[MockModel] = None,
    evaluator: Optional[_MockEvaluator] = None,
    max_iterations: int = 5,
    target_str: Optional[str] = None,
    attacker_system_prompt: Optional[str] = None,
    language_config: Optional[LanguageConfig] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> PAIRAttack:
    """Construct a PAIRAttack with sensible defaults (English config)."""
    return PAIRAttack(
        attacker_model=attacker or MockModel(response=_atk_json("default attack")),
        target_model=target or MockModel(response={"content": "target says no"}),
        evaluator=evaluator or _MockEvaluator(),
        max_iterations=max_iterations,
        target_str=target_str,
        attacker_system_prompt=attacker_system_prompt,
        language_config=language_config or ENGLISH_LANGUAGE_CONFIG,
        name=name,
        description=description,
    )


def _run(attack: PAIRAttack, goal: str, use_async: bool) -> IterativeAttackResult:
    if use_async:
        return asyncio.new_event_loop().run_until_complete(attack.run_attack_async(goal))
    return attack.run_attack(goal)


# ── Constructor / param storage ─────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        pytest.param(
            {},
            {"max_iterations": 20, "target_str": "Sure, here is"},
            id="defaults_english_target_str",
        ),
        pytest.param(
            {"max_iterations": 7, "target_str": "Certainly"},
            {"max_iterations": 7, "target_str": "Certainly"},
            id="custom_numeric_params",
        ),
    ],
)
def test_pair_attack_init_stores_params(kwargs, expected):
    attack = PAIRAttack(
        attacker_model=MockModel(),
        target_model=MockModel(),
        evaluator=_MockEvaluator(),
        language_config=ENGLISH_LANGUAGE_CONFIG,
        **kwargs,
    )

    assert attack.max_iterations == expected["max_iterations"]
    assert attack.target_str == expected["target_str"]


def test_pair_attack_target_str_defaults_to_language_config():
    # No explicit target_str, no override: pulls from language_config.target_str.
    attack = PAIRAttack(
        attacker_model=MockModel(),
        target_model=MockModel(),
        evaluator=_MockEvaluator(),
        language_config=RUSSIAN_LANGUAGE_CONFIG,
    )

    assert attack.target_str == RUSSIAN_LANGUAGE_CONFIG.target_str


def test_pair_attack_custom_attacker_system_prompt_overrides_default():
    custom = "CUSTOM for {goal} -> {target_str}"
    attack = _make_attack(attacker_system_prompt=custom)

    sys_prompt = attack._get_attacker_system_prompt("my-goal")

    assert "CUSTOM for my-goal" in sys_prompt
    assert "DEFAULT" not in sys_prompt
    # Default template marker should not leak in.
    assert "SETTING:" not in sys_prompt


# ── run_attack: success / max_iterations / best-tracking ────────────


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_stops_immediately_on_first_success(use_async):
    # Evaluator declares the very first iteration a success → stop after 1 round.
    attacker = MockModel(response=_atk_json("winning attack"))
    target = MockModel(response={"content": "Sure, here is the answer"})
    evaluator = _MockEvaluator(results=[{"success": True, "score": 1.0}])
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=5,
    )

    result = _run(attack, "goal-x", use_async)

    assert isinstance(result, IterativeAttackResult)
    assert result.success is True
    assert result.best_attack_prompt == "winning attack"
    assert result.best_score == pytest.approx(1.0)
    assert result.total_iterations == 1


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_runs_to_max_iterations_when_no_success(use_async):
    attacker = MockModel(side_effect=lambda p: _atk_json("attack"))
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.1})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=3,
    )

    result = _run(attack, "g", use_async)

    assert result.success is False
    assert result.total_iterations == 3
    assert len(result.iterations) == 3


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_tracks_best_attack_by_highest_score(use_async):
    # Sequence of three attempts with scores 0.3, 0.7, 0.5.
    # Best should be the middle one ("middle") with score 0.7.
    attacker = MockModel(side_effect=[
        _atk_json("first"),
        _atk_json("middle"),
        _atk_json("last"),
    ])
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(results=[
        {"success": False, "score": 0.3},
        {"success": False, "score": 0.7},
        {"success": False, "score": 0.5},
    ])
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=3,
    )

    result = _run(attack, "g", use_async)

    assert result.best_attack_prompt == "middle"
    assert result.best_score == pytest.approx(0.7)


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_records_iterations_with_contiguous_indices(use_async):
    attacker = MockModel(side_effect=lambda p: _atk_json("a"))
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.0})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=4,
    )

    result = _run(attack, "g", use_async)

    iter_numbers = [it.iteration for it in result.iterations]
    assert iter_numbers == list(range(len(result.iterations)))
    assert result.total_iterations == len(result.iterations)


def test_run_attack_falls_back_to_raw_attacker_text_when_no_prompt_field():
    # Attacker emits non-JSON text; _extract_attack should return it verbatim
    # as the attack prompt.
    raw = "this is just plain text, not JSON"
    attacker = MockModel(response={"content": raw})
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.0})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=1,
    )

    result = attack.run_attack("g")

    assert result.iterations[0].attack_prompt == raw
    assert result.success is False


# ── sync/async parity ───────────────────────────────────────────────


def test_run_attack_sync_and_async_produce_same_result_under_identical_mocks():
    attacker_responses = [
        _atk_json("p0"),
        _atk_json("p1"),
        _atk_json("p2"),
    ]
    eval_results = [
        {"success": False, "score": 0.2},
        {"success": False, "score": 0.6},
        {"success": True, "score": 1.0},
    ]

    def _make():
        return _make_attack(
            attacker=MockModel(side_effect=list(attacker_responses)),
            target=MockModel(response={"content": "no"}),
            evaluator=_MockEvaluator(results=list(eval_results)),
            max_iterations=5,
        )

    sync_result = _make().run_attack("g")
    async_result = asyncio.new_event_loop().run_until_complete(_make().run_attack_async("g"))

    assert sync_result.success == async_result.success
    assert sync_result.best_attack_prompt == async_result.best_attack_prompt
    assert sync_result.best_score == pytest.approx(async_result.best_score)
    assert sync_result.total_iterations == async_result.total_iterations


# ── apply / get_params / get_description ────────────────────────────


def test_apply_string_returns_best_attack_prompt_after_refinement():
    attacker = MockModel(response=_atk_json("the best attack"))
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.5})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=1,
    )

    out = attack.apply("user goal")

    assert out == "the best attack"


def test_apply_message_list_appends_best_attack_as_human_message():
    attacker = MockModel(response=_atk_json("payload"))
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.5})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_iterations=1,
    )
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "do thing"},
    ]

    out = attack.apply(msgs)

    assert isinstance(out, list)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[-1] == {"role": "human", "content": "payload"}


def test_get_params_includes_pair_specific_keys_and_attack_type():
    attack = _make_attack(max_iterations=11, target_str="hello")

    params = attack.get_params()

    assert params["attack_type"] == "PAIR"
    assert params["target_str"] == "hello"
    assert params["max_iterations"] == 11
    # Inherited from IterativeAttack.get_params.
    assert "language" in params
    assert params["language"] == "en"


def test_get_description_default_mentions_max_iterations():
    attack = _make_attack(max_iterations=8)

    desc = attack.get_description()

    assert "max 8" in desc or "max_iterations" in desc or "8" in desc


def test_get_description_returns_custom_description_when_provided():
    attack = _make_attack(description="my custom desc")

    assert attack.get_description() == "my custom desc"


# ── module-level constants ──────────────────────────────────────────


def test_default_attacker_system_prompt_has_required_placeholders():
    # .format() in _get_attacker_system_prompt would silently drop these
    # if they were missing from the template.
    assert "{goal}" in DEFAULT_ATTACKER_SYSTEM_PROMPT
    assert "{target_str}" in DEFAULT_ATTACKER_SYSTEM_PROMPT
