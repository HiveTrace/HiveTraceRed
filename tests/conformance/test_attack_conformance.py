"""Auto-discovery conformance tests for all registered attacks.

Automatically discovers all attacks from ATTACK_CLASSES and validates each one
against the BaseAttack contract. No per-attack test code needed — just register
your attack in __init__.py and it gets tested automatically.
"""

from __future__ import annotations

import inspect
import re

import pytest

from hivetracered.attacks.base_attack import BaseAttack
from hivetracered.attacks.model_attack import ModelAttack
from hivetracered.attacks.algo_attack import AlgoAttack
from hivetracered.attacks.iterative_attack import IterativeAttack
from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
from hivetracered.pipeline.constants import ATTACK_CLASSES
from hivetracered.pipeline.create_dataset import build_attack_from_config
from tests.conftest import MockModel, async_collect


# ── Classification & instantiation helpers ──────────────────────────


def classify(attack_class):
    """Return the attack family: 'iterative', 'model', 'algo', or 'template'."""
    if issubclass(attack_class, IterativeAttack):
        return "iterative"
    if issubclass(attack_class, ModelAttack):
        return "model"
    if issubclass(attack_class, AlgoAttack):
        return "algo"
    return "template"


def make_instance(attack_class, family):
    """Instantiate an attack with appropriate mocks."""
    if family == "iterative":
        attacker = MockModel(response={"content": '{"improvement": "test", "prompt": "attack prompt"}'})
        target = MockModel(response={"content": "target response"})
        evaluator = KeywordEvaluator(keywords=["refused", "cannot"])
        return attack_class(
            attacker_model=attacker,
            target_model=target,
            evaluator=evaluator,
            max_iterations=2,
        )
    elif family == "model":
        return attack_class(model=MockModel(response={"content": "transformed prompt"}))
    else:
        return attack_class()


# ── Parametrize over all registered attacks ─────────────────────────

ALL_ATTACKS = [
    (name, info["attack_class"], classify(info["attack_class"]))
    for name, info in ATTACK_CLASSES.items()
    if inspect.isclass(info["attack_class"]) and issubclass(info["attack_class"], BaseAttack)
]


@pytest.mark.parametrize(
    "attack_name,attack_class,family",
    ALL_ATTACKS,
    ids=[a[0] for a in ALL_ATTACKS],
)
class TestAttackConformance:
    """Conformance tests applied to every registered attack."""

    def test_get_name(self, attack_name, attack_class, family):
        attack = make_instance(attack_class, family)
        name = attack.get_name()
        assert isinstance(name, str) and len(name) > 0, (
            f"{attack_name}.get_name() returned {name!r}"
        )

    # ── Prompt placeholder ──────────────────────────────────────

    def test_prompt_placeholder(self, attack_name, attack_class, family):
        # Checks that the attacker prompt / template contains at least one
        # {prompt…} placeholder (e.g. {prompt}, {prompt_first_half}).
        # The regex r'\{prompt[^}]*\}' matches the standard {prompt} and
        # legitimate split-prompt variants ({prompt_first_half}, etc.)
        # without accepting any other curly-braced identifier.
        if family == "iterative":
            pytest.skip("Iterative attacks use system prompts, not {prompt} templates")
        attack = make_instance(attack_class, family)
        if family == "model":
            assert re.search(r'\{prompt[^}]*\}', attack.attacker_prompt), (
                f"{attack_name}.attacker_prompt missing {{prompt}} placeholder"
            )
        elif hasattr(attack, "template") and attack.template:
            assert re.search(r'\{prompt[^}]*\}', attack.template), (
                f"{attack_name}.template missing prompt placeholder"
            )

    # ── apply(message list) ─────────────────────────────────────

    def test_apply_preserves_history(self, attack_name, attack_class, family):
        attack = make_instance(attack_class, family)
        msgs = [
            {"role": "system", "content": "You are a helper."},
            {"role": "human", "content": "test prompt"},
        ]
        result = attack.apply(msgs)
        assert isinstance(result, list)
        assert len(result) >= 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helper."

    # ── stream_abatch ───────────────────────────────────────────

    def test_stream_abatch_order(self, attack_name, attack_class, family):
        prompts = [f"prompt {i}" for i in range(5)]
        if family == "model":
            responses = [{"content": f"response {i}"} for i in range(5)]
            model = MockModel(side_effect=list(responses))
            attack = attack_class(model=model)
        else:
            attack = make_instance(attack_class, family)
        results = async_collect(attack.stream_abatch(prompts))
        assert len(results) == 5, (
            f"{attack_name}.stream_abatch returned {len(results)} results, expected 5"
        )
        if family == "iterative":
            # Iterative attacks use multi-step loops; the per-prompt
            # ordering invariant is not meaningful — length contract only.
            return
        for i, result in enumerate(results):
            if family == "model":
                assert f"response {i}" in str(result), (
                    f"{attack_name}.stream_abatch result {i} does not match expected order"
                )

    # ── Registration ────────────────────────────────────────────
    # Registration is tautological here: ALL_ATTACKS is built from
    # ATTACK_CLASSES, and test_pipeline_wiring exercises the same lookup
    # via build_attack_from_config(attack_name).

    # ── Pipeline wiring ─────────────────────────────────────────

    def test_pipeline_wiring(self, attack_name, attack_class, family):
        mock = MockModel(response={"content": "transformed prompt"})
        if family == "iterative":
            attacker = MockModel(response={"content": '{"improvement": "test", "prompt": "attack prompt"}'})
            target = MockModel(response={"content": "target response"})
            attack = build_attack_from_config(
                attack_name,
                attacker_model=attacker,
                target_model=target,
                evaluation_model=mock,
            )
        elif family == "model":
            attack = build_attack_from_config(attack_name, attacker_model=mock)
        else:
            attack = build_attack_from_config(attack_name)
        assert isinstance(attack, attack_class)
