"""Unit tests for hivetracered.attacks.types.iterative.tap_attack.TAPAttack.

Covers TAP-specific behavior: tree branching, pruning, language-config switching,
metadata construction, sync + async run paths, and the JSON extraction fallback
when the attacker model emits an unparseable response.

Mocking discipline: only architectural seams are mocked (attacker model, target
model, evaluator). The TAP class itself, ``_extract_attack``, ``_create_node``,
and the tree expansion logic are exercised, never patched.
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
from hivetracered.attacks.types.iterative.tap_attack import (
    DEFAULT_TAP_ATTACKER_PROMPT,
    TAPAttack,
    TreeNode,
)
from hivetracered.evaluators.base_evaluator import BaseEvaluator
from tests.conftest import MockModel


# ── Test doubles ────────────────────────────────────────────────────


class _MockEvaluator(BaseEvaluator):
    """Controllable evaluator that returns a queue of (score, success) results.

    This is a deliberate test double for the evaluator architectural seam.
    Behavior:
      - ``evaluate`` and ``stream_abatch`` consume from ``results``.
      - When ``results`` is exhausted, returns ``default``.
    """

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
    max_iterations: int = 50,
    max_depth: int = 2,
    branching_factor: int = 2,
    prune_threshold: float = 0.4,
    language_config: Optional[LanguageConfig] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    attacker_system_prompt: Optional[str] = None,
) -> TAPAttack:
    """Construct a TAPAttack with sensible defaults (English config, no clamps)."""
    return TAPAttack(
        attacker_model=attacker or MockModel(response=_atk_json("default attack")),
        target_model=target or MockModel(response={"content": "target says no"}),
        evaluator=evaluator or _MockEvaluator(),
        max_iterations=max_iterations,
        max_depth=max_depth,
        branching_factor=branching_factor,
        prune_threshold=prune_threshold,
        attacker_system_prompt=attacker_system_prompt,
        language_config=language_config or ENGLISH_LANGUAGE_CONFIG,
        name=name,
        description=description,
    )


# ── Constructor / param storage ─────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs, expected, expected_prompt",
    [
        pytest.param(
            {},
            {"max_depth": 4, "branching_factor": 3, "prune_threshold": 0.4, "max_iterations": 15},
            DEFAULT_TAP_ATTACKER_PROMPT,
            id="defaults",
        ),
        pytest.param(
            {"max_iterations": 7, "max_depth": 3, "branching_factor": 4, "prune_threshold": 0.25},
            {"max_depth": 3, "branching_factor": 4, "prune_threshold": 0.25, "max_iterations": 7},
            DEFAULT_TAP_ATTACKER_PROMPT,
            id="custom_numeric_params",
        ),
        pytest.param(
            {"attacker_system_prompt": "CUSTOM SYSTEM PROMPT for goal: {goal}"},
            {"max_depth": 4, "branching_factor": 3, "prune_threshold": 0.4, "max_iterations": 15},
            "CUSTOM SYSTEM PROMPT for goal: {goal}",
            id="custom_attacker_system_prompt",
        ),
    ],
)
def test_tap_attack_init_stores_params_and_attacker_prompt(kwargs, expected, expected_prompt):
    attack = TAPAttack(
        attacker_model=MockModel(),
        target_model=MockModel(),
        evaluator=_MockEvaluator(),
        **kwargs,
    )

    assert attack.max_depth == expected["max_depth"]
    assert attack.branching_factor == expected["branching_factor"]
    assert attack.prune_threshold == pytest.approx(expected["prune_threshold"])
    assert attack.max_iterations == expected["max_iterations"]
    # attacker_system_prompt: defaults to DEFAULT_TAP_ATTACKER_PROMPT, accepts override.
    assert attack.attacker_system_prompt == expected_prompt



# ── _create_initial_prompt / _create_branch_prompt ──────────────────


def test_create_initial_prompt_handles_language_config():
    # Only the Russian case is tested here because the English config has an
    # empty attacker_suffix (""), so asserting "ВАЖНОЕ ДОПОЛНЕНИЕ" not in prompt
    # is vacuous — appending "" cannot introduce that string regardless of the
    # if-guard. Russian config has a non-empty suffix, so both the presence of
    # "OBJECTIVE:" and the suffix addition are truly exercised.
    config = RUSSIAN_LANGUAGE_CONFIG
    goal = "цель"
    attack = _make_attack(language_config=config)

    prompt = attack._create_initial_prompt(goal)

    assert f"OBJECTIVE: {goal}" in prompt
    assert config.attacker_suffix in prompt


def test_create_branch_prompt_includes_parent_context_and_optional_suffix():
    # Only the Russian case is tested here. The English config has attacker_suffix=""
    # so asserting "ВАЖНОЕ ДОПОЛНЕНИЕ" not in prompt is vacuous (appending "" cannot
    # introduce that string). The Russian config has a non-empty suffix, so both the
    # parent-context strings and the suffix addition are genuinely exercised.
    config = RUSSIAN_LANGUAGE_CONFIG
    attack = _make_attack(language_config=config)

    prompt = attack._create_branch_prompt(
        goal="g",
        parent_attack="parent_atk",
        parent_response="parent_resp",
        parent_score=0.6,
        branch_index=0,
    )

    assert "PREVIOUS PROMPT: parent_atk" in prompt
    assert "LANGUAGE MODEL OUTPUT: parent_resp" in prompt
    assert "OBJECTIVE: g" in prompt
    # _scale_score(0.6) = int(0.6 * 10) = 6, clamped to [1, 10].
    assert "PREVIOUS SCORE: 6" in prompt
    assert config.attacker_suffix in prompt


def test_create_branch_prompt_rotates_hints_by_branch_index_modulo_len():
    config = ENGLISH_LANGUAGE_CONFIG
    attack = _make_attack(language_config=config)
    hints = config.approach_hints
    n_hints = len(hints)
    other_idx = next(i for i in range(1, n_hints))

    p_zero = attack._create_branch_prompt("g", "a", "r", 0.0, branch_index=0)
    p_other = attack._create_branch_prompt("g", "a", "r", 0.0, branch_index=other_idx)
    p_wrap = attack._create_branch_prompt("g", "a", "r", 0.0, branch_index=n_hints)

    # branch_idx 0 → hints[0]; branch_idx i → hints[i]; branch_idx n_hints wraps to hints[0].
    assert hints[0] in p_zero
    assert hints[other_idx] in p_other
    assert hints[0] not in p_other
    assert hints[0] in p_wrap


# ── _create_node ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "attacker_response, expected_improvement, attach_parent",
    [
        pytest.param(
            json.dumps({"improvement": "be subtler", "prompt": "p"}),
            "be subtler",
            True,
            id="valid_json_with_parent",
        ),
        pytest.param(
            "!!! not JSON, no improvement field !!!",
            "",
            False,
            id="unparseable_no_parent",
        ),
    ],
)
def test_create_node_parses_improvement_and_optionally_attaches_to_parent(
    attacker_response, expected_improvement, attach_parent
):
    attack = _make_attack()
    parent = TreeNode(attack_prompt="root", depth=0) if attach_parent else None

    node = attack._create_node(
        attack_prompt="child_atk",
        response="child_resp",
        score=0.5,
        depth=1,
        attacker_response=attacker_response,
        parent=parent,
    )

    assert node.improvement == expected_improvement
    assert node.pruned is False
    if attach_parent:
        assert node.parent is parent
        assert node in parent.children
    else:
        assert node.parent is None


# ── run_attack: success / pruning / depth termination ───────────────


def _run(attack: TAPAttack, goal: str, use_async: bool) -> IterativeAttackResult:
    if use_async:
        return asyncio.new_event_loop().run_until_complete(attack.run_attack_async(goal))
    return attack.run_attack(goal)


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_returns_immediately_when_root_succeeds(use_async):
    # Evaluator declares root attempt a success; we should bail out at depth 0.
    # Both sync and async paths share _record_root, so both must short-circuit.
    attacker = MockModel(response=_atk_json("root attack"))
    target = MockModel(response={"content": "Sure, here is the answer"})
    evaluator = _MockEvaluator(results=[{"success": True, "score": 1.0}])
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=4, branching_factor=3,
    )

    result = _run(attack, "goal-x", use_async)

    assert isinstance(result, IterativeAttackResult)
    assert result.success is True
    assert result.best_attack_prompt == "root attack"
    assert result.best_score == pytest.approx(1.0)
    assert result.total_iterations == 1
    assert result.metadata["max_depth_reached"] == 0
    assert result.metadata["success_depth"] == 0
    # No pruning metadata in the success branch.
    assert "prune_threshold" not in result.metadata


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_prunes_low_scoring_children_and_does_not_expand_them(use_async):
    # All children of root score below prune_threshold → next_level empty.
    # Sync prune in _record_child; async prune in _record_async_result — same contract.
    attacker = MockModel(side_effect=lambda p: _atk_json("atk"))
    target = MockModel(response={"content": "still refusing"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.1})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=3, branching_factor=2, prune_threshold=0.5,
    )

    result = _run(attack, "g", use_async)

    # 1 root + 2 depth-1 children = 3 iterations; depth 2 is skipped because
    # the level was emptied by pruning.
    assert result.success is False
    assert result.total_iterations == 3  # = 1 root + 2 children, all pruned
    assert result.metadata["prune_threshold"] == pytest.approx(0.5)
    assert result.metadata["branching_factor"] == 2


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_respects_max_iterations_cap(use_async):
    # Sync caps in _expand_parent_sync; async caps in _launch_depth_tasks.
    attacker = MockModel(side_effect=lambda p: _atk_json("a"))
    target = MockModel(response={"content": "no"})
    # All scores high enough to survive pruning, so the only stopping criterion
    # is max_iterations.
    evaluator = _MockEvaluator(default={"success": False, "score": 0.9})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=10, branching_factor=2, prune_threshold=0.0,
        max_iterations=3,
    )

    result = _run(attack, "g", use_async)

    # The cap must hold: total_iterations ≤ max_iterations.
    assert result.total_iterations <= 3  # = max_iterations
    assert result.success is False


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_run_attack_tracks_best_attack_and_score_by_highest(use_async):
    # Sequence: root score 0.5 → two children (0.6, 0.8). Best is the second
    # child with score 0.8 and prompt "winner".
    # Sync best-tracking lives in _record_child; async best-tracking lives in
    # _record_async_result — both must select the highest-scoring branch.
    attacker = MockModel(side_effect=[
        _atk_json("root_attack"),
        _atk_json("loser"),
        _atk_json("winner"),
    ])
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(results=[
        {"success": False, "score": 0.5},  # root
        {"success": False, "score": 0.6},  # child 0
        {"success": False, "score": 0.8},  # child 1
    ])
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=1, branching_factor=2, prune_threshold=0.0,
    )

    result = _run(attack, "g", use_async)

    assert result.best_attack_prompt == "winner"
    assert result.best_score == pytest.approx(0.8)


def test_run_attack_falls_back_to_raw_attacker_text_when_no_prompt_field():
    # Attacker response is not parseable JSON and has no "prompt" field; the
    # base class _extract_attack should return the raw response verbatim.
    raw = "this is just plain text, not JSON"
    attacker = MockModel(response={"content": raw})
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.0})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=0, branching_factor=1, prune_threshold=1.0,  # immediately prune
    )

    result = attack.run_attack("g")

    # Root attack prompt is the raw attacker text.
    assert result.iterations[0].attack_prompt == raw
    assert result.success is False


def test_run_attack_success_at_depth_one_records_success_depth():
    # Root scores below threshold's success bar but above prune; one child wins.
    attacker = MockModel(side_effect=[
        _atk_json("root"),
        _atk_json("good child"),
    ])
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(results=[
        {"success": False, "score": 0.5},  # root, survives
        {"success": True, "score": 1.0},   # child success
    ])
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=2, branching_factor=1, prune_threshold=0.4,
    )

    result = attack.run_attack("g")

    assert result.success is True
    assert result.metadata["success_depth"] == 1  # = depth where success occurred
    assert result.best_attack_prompt == "good child"


# ── async path ──────────────────────────────────────────────────────


def test_run_attack_async_iterations_are_numbered_contiguously():
    attacker = MockModel(side_effect=lambda p: _atk_json("a"))
    target = MockModel(response={"content": "no"})
    evaluator = _MockEvaluator(default={"success": False, "score": 0.6})
    attack = _make_attack(
        attacker=attacker, target=target, evaluator=evaluator,
        max_depth=1, branching_factor=3, prune_threshold=0.0,
    )

    result = asyncio.new_event_loop().run_until_complete(attack.run_attack_async("g"))

    iter_numbers = [it.iteration for it in result.iterations]
    assert iter_numbers == list(range(len(result.iterations)))
    assert result.total_iterations == len(result.iterations)


# ── apply / get_params / get_description ────────────────────────────



def test_get_params_includes_tap_specific_keys_and_attack_type():
    attack = _make_attack(
        max_depth=5, branching_factor=2, prune_threshold=0.3,
        max_iterations=11,
    )

    params = attack.get_params()

    assert params["attack_type"] == "TAP"
    assert params["max_depth"] == 5
    assert params["branching_factor"] == 2
    assert params["prune_threshold"] == pytest.approx(0.3)
    # Inherited from IterativeAttack.get_params.
    assert params["max_iterations"] == 11
    assert "language" in params
    assert params["language"] == "en"  # we passed ENGLISH_LANGUAGE_CONFIG


def test_get_description_default_includes_depth_branching_and_threshold():
    attack = _make_attack(max_depth=3, branching_factor=4, prune_threshold=0.2)

    desc = attack.get_description()

    assert "depth=3" in desc
    assert "branching=4" in desc
    assert "prune_threshold=0.2" in desc


def test_get_description_returns_custom_description_when_provided():
    attack = _make_attack(description="my custom desc")

    assert attack.get_description() == "my custom desc"
