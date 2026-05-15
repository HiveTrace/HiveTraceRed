"""Tests for hivetracered.attacks.iterative_attack.IterativeAttack.

Covers behaviors defined directly on IterativeAttack (not on any concrete
subclass): the language_config default, and the apply() / _format_result()
interface that maps run_attack output back to the caller's prompt type.

TAPAttack is used as the concrete vehicle because it is the only complete
IterativeAttack subclass available without additional mocking; the tests below
assert behavior that belongs to IterativeAttack, not to TAP.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Optional

from hivetracered.attacks.iterative_attack import RUSSIAN_LANGUAGE_CONFIG
from hivetracered.attacks.types.iterative.tap_attack import TAPAttack
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from tests.conftest import MockModel


# ── Minimal test double ─────────────────────────────────────────────


class _MockEvaluator(BaseEvaluator):
    def __init__(self, default: Optional[Dict[str, Any]] = None):
        self.default = default or {"success": False, "score": 0.1}

    def evaluate(self, prompt, response):
        return dict(self.default)

    async def stream_abatch(self, prompts, responses) -> AsyncGenerator[Dict[str, Any], None]:
        for _ in zip(prompts, responses):
            yield dict(self.default)

    def get_name(self) -> str:
        return "MockEvaluator"

    def get_description(self) -> str:
        return "test double"

    def get_params(self) -> Dict[str, Any]:
        return {}


def _atk_json(prompt_text: str) -> Dict[str, Any]:
    return {"content": json.dumps({"improvement": "x", "prompt": prompt_text})}


def _make_tap(**kwargs) -> TAPAttack:
    return TAPAttack(
        attacker_model=MockModel(response=_atk_json("attack")),
        target_model=MockModel(response={"content": "no"}),
        evaluator=_MockEvaluator(),
        max_depth=0,
        branching_factor=1,
        prune_threshold=1.0,
        **kwargs,
    )


# ── Inherited IterativeAttack behaviors ─────────────────────────────


def test_language_config_defaults_to_russian():
    attack = _make_tap()
    assert attack.language_config is RUSSIAN_LANGUAGE_CONFIG
    assert attack.language_config.code == "ru"


def test_apply_string_returns_best_attack_prompt():
    # Root score 0.1 > best_score's initial 0.0 → best_attack is set.
    attacker = MockModel(response=_atk_json("the best attack"))
    attack = TAPAttack(
        attacker_model=attacker,
        target_model=MockModel(response={"content": "no"}),
        evaluator=_MockEvaluator(default={"success": False, "score": 0.1}),
        max_depth=0,
        branching_factor=1,
        prune_threshold=1.0,
    )

    out = attack.apply("user goal")

    assert out == "the best attack"


def test_apply_message_list_appends_best_attack_as_human_message():
    attacker = MockModel(response=_atk_json("payload"))
    attack = TAPAttack(
        attacker_model=attacker,
        target_model=MockModel(response={"content": "no"}),
        evaluator=_MockEvaluator(default={"success": False, "score": 0.1}),
        max_depth=0,
        branching_factor=1,
        prune_threshold=1.0,
    )
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "do thing"},
    ]

    out = attack.apply(msgs)

    assert isinstance(out, list)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[-1] == {"role": "human", "content": "payload"}
