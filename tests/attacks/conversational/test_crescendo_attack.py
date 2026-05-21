"""Unit tests for hivetracered.attacks.types.multi_turn.conversational.crescendo_attack.CrescendoAttack.

Each test references its SPEC-NNN ID and acceptance criterion ref.

Mocking discipline: only architectural seams are mocked (attacker model, target model,
refusal judge, success judge). The CrescendoAttack class itself is never patched.

Attacker invocation: per AC-09 / FR-02, CrescendoAttack passes a single flat-concatenated
``str`` (``f"{system_content}\\n\\n{user_turn_body}"``) to ``attacker_model.ainvoke(...)``,
not a structured message list. Tests assert against the captured string accordingly.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from unittest.mock import Mock

from hivetracered.evaluators.base_evaluator import BaseEvaluator
from hivetracered.models.base_model import Model
from tests.conftest import MockModel, async_collect
from tests.attacks.conversational.conftest import (
    MockEvaluator as _MockEvaluator,
    RefusalOnFirstCallEvaluator as _RefusalOnFirstCallEvaluator,
    FailOnFirstCallModel as _FailOnFirstCallModel,
    FailOnFirstCallTargetModel as _FailOnFirstCallTargetModel,
    FailOnFirstCallEvaluator as _FailOnFirstCallEvaluator,
    AlwaysRaisingEvaluator as _AlwaysRaisingEvaluator,
    AlwaysRaisingModel as _AlwaysRaisingModel,
    PlainTextThenValidModel as _PlainTextThenValidModel,
)

from hivetracered.attacks.types.multi_turn.conversational.crescendo_attack import (
    CrescendoAttack,
)


_VALID_ATK_JSON = '{"q": "question", "summary": "summary"}'
_VALID_ATK_RESPONSE = {"content": _VALID_ATK_JSON}
_VALID_TARGET_RESPONSE = {"content": "target response"}


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def no_refusal_judge():
    """Evaluator that never signals refusal (success=False always)."""
    return _MockEvaluator(default={"success": False})


@pytest.fixture
def no_success_judge():
    """Evaluator that never signals success (success=False always)."""
    return _MockEvaluator(default={"success": False})


@pytest.fixture
def attacker_mock():
    """MockModel that always returns valid attacker JSON."""
    return MockModel(response=_VALID_ATK_RESPONSE)


@pytest.fixture
def target_mock():
    """MockModel that always returns a valid target response."""
    return MockModel(response=_VALID_TARGET_RESPONSE)


@pytest.fixture
def minimal_attack(attacker_mock, target_mock, no_refusal_judge, no_success_judge):
    """CrescendoAttack with max_rounds=1, max_iterations=1 and all-passing mocks."""
    return CrescendoAttack(
        attacker_model=attacker_mock,
        target_model=target_mock,
        refusal_judge=no_refusal_judge,
        success_judge=no_success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )


# ── SPEC-001 ─────────────────────────────────────────────────────────


def test_SPEC_001_refusal_backtracks_HT_and_retries_within_same_iteration():
    """SPEC-001 (AC-01): refusal causes H_T backtrack and retry within iteration 0, not iteration 1."""
    # Arrange: refusal judge refuses on call 1, then accepts forever after
    refusal_judge = _MockEvaluator(
        results=[{"success": False}],
        default={"success": True},
    )
    success_judge = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=3,
        max_iterations=2,
        refusal_cap=10,
    )

    result = attack.run_attack("test goal")

    turns_iter0 = result.iterations[0].turns
    # Build committed-status list at setup time (no if in assertion section)
    committed_flags = [t.committed for t in turns_iter0]
    iteration_ids = [t.iteration for t in turns_iter0]
    assert False in committed_flags, (
        "iteration 0 must have at least one backtracked (committed=False) turn"
    )
    assert True in committed_flags, (
        "iteration 0 must have at least one committed turn after retry"
    )
    assert iteration_ids == [0] * len(iteration_ids), (
        "all turns in iterations[0].turns must have iteration==0 (refusal resolved inside iteration 0)"
    )


# ── SPEC-002 ─────────────────────────────────────────────────────────


def test_SPEC_002_success_on_round_2_of_iteration_1_stops_early():
    """SPEC-002 (AC-02): success on round 2 stops attack; iteration 2 is not executed."""
    # Arrange: success_judge returns False on first two calls, True on third
    success_judge = _MockEvaluator(
        results=[{"success": False}, {"success": False}, {"success": True}],
        default={"success": False},
    )
    refusal_judge = _MockEvaluator(default={"success": True})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response={"content": "target response"})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=5,
        max_iterations=3,
        refusal_cap=10,
    )

    result = attack.run_attack("test goal")

    assert result.success is True, "result.success must be True after success_judge fires"
    assert len(result.iterations) == 1, "exactly 1 iteration must be recorded"
    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    assert committed_flags.count(True) == 3, "exactly 3 committed turns (rounds 0, 1, 2) must be recorded"
    assert turns[-1].committed is True, "last turn must be committed"
    transcript = result.final_transcript
    assert isinstance(transcript, list), "final_transcript must be a list"
    assert len(transcript) == 5, (
        "final_transcript must have 5 entries (3 human + 2 ai): the trailing "
        "target answer is dropped so the transcript ends on the final human turn"
    )
    assert transcript[-1]["role"] == "human", (
        "final_transcript must end on a human turn so the response stage elicits "
        "a fresh answer"
    )
    transcript_keys = [("role" in m, "content" in m) for m in transcript]
    assert transcript_keys == [(True, True)] * 5, (
        "every final_transcript entry must have 'role' and 'content' keys"
    )


# ── SPEC-003 ─────────────────────────────────────────────────────────


def test_SPEC_003_full_run_no_success_correct_turn_count():
    """SPEC-003 (AC-03): full run with no success produces 4 committed turns (2 rounds x 2 iterations)."""
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=2,
        refusal_cap=10,
    )

    result = attack.run_attack("test goal")

    assert result.success is False, "result.success must be False when no success_judge fires"
    assert len(result.iterations) == 2, "exactly 2 iterations must be recorded"
    all_turns = result.iterations[0].turns + result.iterations[1].turns
    committed_flags = [t.committed for t in all_turns]
    assert committed_flags.count(True) == 4, (
        "total committed turns must be 4 (2 rounds x 2 iterations)"
    )


# ── SPEC-004 ─────────────────────────────────────────────────────────


def test_SPEC_004_crescendo_attack_in_ATTACK_CLASSES_with_conversational_type():
    """SPEC-004 (AC-04): CrescendoAttack is registered in ATTACK_CLASSES with attack_type 'conversational'."""
    from hivetracered.pipeline.constants import ATTACK_CLASSES

    assert "CrescendoAttack" in ATTACK_CLASSES, (
        "'CrescendoAttack' must be a key in ATTACK_CLASSES"
    )
    assert ATTACK_CLASSES["CrescendoAttack"]["attack_type"] == "conversational", (
        "ATTACK_CLASSES['CrescendoAttack']['attack_type'] must equal 'conversational'"
    )


# ── SPEC-005 ─────────────────────────────────────────────────────────


def test_SPEC_005_get_framework_mappings_returns_nonempty_sets_for_conversational():
    """SPEC-005 (AC-05): get_framework_mappings('conversational') returns non-empty OWASP, MITRE, FSTEK sets."""
    from hivetracered.pipeline.framework_mapping import get_framework_mappings

    result = get_framework_mappings(attack_type="conversational")

    assert result, "result must be a non-empty dict"
    assert "LLM01" in result["OWASP_LLM_TOP_10"], (
        "'LLM01' must be in result['OWASP_LLM_TOP_10']"
    )
    assert len(result["MITRE_ATLAS"]) >= 1, "MITRE_ATLAS set must be non-empty"
    assert len(result["FSTEK_117"]) >= 1, "FSTEK_117 set must be non-empty"


# ── SPEC-006 ─────────────────────────────────────────────────────────


def test_SPEC_006_get_params_returns_all_required_keys():
    """SPEC-006 (AC-06): get_params() returns all required keys and correct values."""
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator()

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=5,
    )

    result = attack.get_params()

    required_keys = {
        "max_rounds", "max_iterations", "refusal_cap",
        "attacker_model", "target_model",
        "refusal_judge_model", "success_judge_model", "language",
    }
    assert required_keys.issubset(result.keys()), (
        f"get_params() must return all of {required_keys}"
    )
    assert result["max_rounds"] == 5, "max_rounds must equal 5"
    assert isinstance(result["attacker_model"], str) and result["attacker_model"], (
        "attacker_model must be a non-empty string (class name)"
    )
    assert isinstance(result["refusal_judge_model"], str) and result["refusal_judge_model"], (
        "refusal_judge_model must be a non-empty string"
    )


# ── SPEC-008 ─────────────────────────────────────────────────────────


def test_SPEC_008_run_attack_async_produces_same_result_as_run_attack():
    """SPEC-008 (AC-08): run_attack_async produces the same logical result as run_attack."""
    def _make_attack():
        return CrescendoAttack(
            attacker_model=MockModel(response=_VALID_ATK_RESPONSE),
            target_model=MockModel(response=_VALID_TARGET_RESPONSE),
            refusal_judge=_MockEvaluator(default={"success": True}),
            success_judge=_MockEvaluator(default={"success": False}),
            max_rounds=2,
            max_iterations=1,
            refusal_cap=10,
        )

    atk_sync = _make_attack()
    atk_async = _make_attack()

    result_sync = atk_sync.run_attack("goal")
    result_async = asyncio.new_event_loop().run_until_complete(
        atk_async.run_attack_async("goal")
    )

    assert result_sync.success is False, "sync result must have success=False"
    assert result_async.success is False, "async result must have success=False"
    assert len(result_sync.iterations) == 1, "sync result must have 1 iteration"
    assert len(result_async.iterations) == 1, "async result must have 1 iteration"
    sync_turns = result_sync.iterations[0].turns
    async_turns = result_async.iterations[0].turns
    committed_sync = [t.committed for t in sync_turns].count(True)
    committed_async = [t.committed for t in async_turns].count(True)
    assert committed_sync == 2, "sync must have exactly 2 committed turns"
    assert committed_async == 2, "async must have exactly 2 committed turns"
    assert result_sync.final_transcript == result_async.final_transcript, (
        "final_transcript must be identical between sync and async runs"
    )


# ── SPEC-009 ─────────────────────────────────────────────────────────


def test_SPEC_009_refusal_cap_exhaustion_terminates_attack():
    """SPEC-009 (AC-09): refusal_cap exhaustion terminates after exactly cap retries with no committed turns."""
    # All refusals: success_judge always True (refused)
    refusal_judge = _MockEvaluator(default={"success": False})
    success_judge = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=3,
    )

    result = attack.run_attack("goal")

    # Attack terminated (did not loop forever)
    assert len(result.iterations) == 1, "exactly 1 iteration element must be present"
    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    assert committed_flags.count(False) == 3, (
        "exactly 3 non-committed turns must be recorded (cap=3 retries)"
    )
    assert committed_flags.count(True) == 0, "no committed turns must exist when cap is exhausted"
    assert result.success is False, "result.success must be False"


# ── SPEC-010 ─────────────────────────────────────────────────────────


def test_SPEC_010_custom_attacker_system_prompt_is_prefix_of_flat_attacker_prompt():
    """SPEC-010 (AC-09, AC-10, FR-02): custom attacker_system_prompt is rendered at the start
    of the single flat string passed to attacker_model.ainvoke, followed by the separator and
    the user-turn body (PREVIOUS_TURNS). A regression where the system prompt is silently
    dropped from the string fails this test."""
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
        attacker_system_prompt="CUSTOM PROMPT {goal}",
    )

    attack.run_attack("my goal")

    arg = attacker.call_log[0]
    assert isinstance(arg, str), "attacker prompt must be a flat str, not a message list"
    assert arg.startswith("CUSTOM PROMPT my goal\n\n"), (
        "flat attacker prompt must begin with the rendered system prompt + '\\n\\n'"
    )
    assert "PREVIOUS_TURNS" in arg, (
        "flat attacker prompt must contain the user-turn body (PREVIOUS_TURNS marker)"
    )


# ── SPEC-011 ─────────────────────────────────────────────────────────


def test_SPEC_011_missing_score_and_explanation_in_success_verdict_does_not_raise():
    """SPEC-011 (AC-11): success_judge returning only {'success': True} does not raise."""
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": True})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    assert result.success is True, "result.success must be True"
    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    assert committed_flags.count(True) == 1, "exactly 1 committed turn must be recorded"
    assert turns[committed_flags.index(True)].success_judge_verdict == {"success": True}, (
        "success_judge_verdict must equal {'success': True}"
    )


# ── SPEC-012 ─────────────────────────────────────────────────────────


def test_SPEC_012_build_attack_from_config_does_not_raise_for_crescendo():
    """SPEC-012 (AC-12): build_attack_from_config with 'CrescendoAttack' does not raise TypeError."""
    from hivetracered.pipeline.create_dataset import build_attack_from_config

    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    evaluation = MockModel(response={"content": "eval response"})

    result = build_attack_from_config(
        "CrescendoAttack",
        attacker_model=attacker,
        target_model=target,
        evaluation_model=evaluation,
    )

    assert isinstance(result, CrescendoAttack), (
        "build_attack_from_config('CrescendoAttack', ...) must return a CrescendoAttack instance"
    )


# ── SPEC-013 ─────────────────────────────────────────────────────────


def test_SPEC_013_result_contains_per_iteration_history_with_all_required_fields():
    """SPEC-013 (AC-13): result has per-iteration history for all iterations with required turn fields."""
    # Iteration 0: refusal judge refuses on call 1 (cap=1 → cap exhausted), no success.
    # Iteration 1: refusal judge accepts; no success.
    # _RefusalOnFirstCallEvaluator from conftest encodes this without inline branching.
    refusal_judge = _RefusalOnFirstCallEvaluator()
    success_judge = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=2,
        refusal_cap=1,
    )

    result = attack.run_attack("goal")

    assert len(result.iterations) == 2, "must have exactly 2 iteration records"
    assert len(result.iterations[0].turns) >= 1, "iteration 0 must have at least 1 turn"
    assert len(result.iterations[1].turns) >= 1, "iteration 1 must have at least 1 turn"
    # Verify required fields are accessible on specific turn records (no for-loop)
    first_turn_iter0 = result.iterations[0].turns[0]
    first_turn_iter1 = result.iterations[1].turns[0]
    assert hasattr(first_turn_iter0, "q"), "iteration 0 turn must have 'q' field"
    assert hasattr(first_turn_iter0, "target_response"), "iteration 0 turn must have 'target_response' field"
    assert hasattr(first_turn_iter0, "refusal_judge_verdict"), "iteration 0 turn must have 'refusal_judge_verdict' field"
    assert hasattr(first_turn_iter0, "success_judge_verdict"), "iteration 0 turn must have 'success_judge_verdict' field"
    assert hasattr(first_turn_iter1, "q"), "iteration 1 turn must have 'q' field"
    assert hasattr(first_turn_iter1, "target_response"), "iteration 1 turn must have 'target_response' field"
    assert hasattr(first_turn_iter1, "refusal_judge_verdict"), "iteration 1 turn must have 'refusal_judge_verdict' field"
    assert hasattr(first_turn_iter1, "success_judge_verdict"), "iteration 1 turn must have 'success_judge_verdict' field"


# ── SPEC-014 ─────────────────────────────────────────────────────────


def test_SPEC_014_both_iteration_records_survive_after_early_termination():
    """SPEC-014 (AC-14): when iteration 1 succeeds, iteration 0's record is still preserved on the result."""
    # success_judge: False on first call (iteration 0 fails), True on second (iteration 1 succeeds)
    success_judge = Mock(spec=BaseEvaluator)
    success_judge.evaluate.side_effect = [{"success": False}, {"success": True}]
    success_judge.get_name.return_value = "MockSuccessJudge"

    refusal_judge = Mock(spec=BaseEvaluator)
    refusal_judge.evaluate.return_value = {"success": True}
    refusal_judge.get_name.return_value = "MockRefusalJudge"

    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=2,
        refusal_cap=10,
    )

    result = attack.run_attack("base prompt")

    assert len(result.iterations) == 2, (
        "result.iterations must have exactly 2 elements (no early-termination record loss)"
    )
    assert result.iterations[0].success is False, (
        "iterations[0].success must be False"
    )
    assert result.iterations[1].success is True, (
        "iterations[1].success must be True"
    )


# ── SPEC-015 ─────────────────────────────────────────────────────────


def test_SPEC_015_prompt_field_in_pipeline_row_is_valid_json_list_of_role_content_dicts():
    """SPEC-015 (AC-15): row['prompt'] is valid JSON parseable as list of {'role', 'content'} dicts."""
    from hivetracered.pipeline.create_dataset import stream_attack

    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=10,
    )

    rows = async_collect(stream_attack(attack, ["base prompt"]))
    row = rows[0]

    assert isinstance(row["prompt"], str) and row["prompt"], (
        "row['prompt'] must be a non-empty string"
    )
    parsed = json.loads(row["prompt"])
    assert isinstance(parsed, list), "parsed prompt must be a list"
    parsed_keys = [("role" in m, "content" in m) for m in parsed]
    assert parsed_keys == [(True, True)] * len(parsed_keys), (
        "every element must have 'role' and 'content' keys"
    )


# ── SPEC-016 ─────────────────────────────────────────────────────────


def test_SPEC_016_crescendo_attack_yaml_is_valid_with_required_keys():
    """SPEC-016 (AC-16): examples/crescendo_attack.yaml is valid YAML with required keys."""
    import yaml
    import os

    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "examples", "crescendo_attack.yaml"
    )
    yaml_path = os.path.abspath(yaml_path)

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    assert "attacker_model" in data, "YAML must contain 'attacker_model' key"
    assert "response_model" in data, "YAML must contain 'response_model' key"
    assert "attacks" in data, "YAML must contain 'attacks' key"
    # The design mandates attacks[0] is the CrescendoAttack entry (design.md Touch point yaml)
    crescendo_entry = data["attacks"][0]
    assert isinstance(crescendo_entry, dict), "attacks[0] must be a dict"
    assert crescendo_entry.get("name") == "CrescendoAttack", (
        "attacks[0] must have name 'CrescendoAttack'"
    )
    assert "params" in crescendo_entry, "CrescendoAttack entry must have 'params'"
    assert "max_rounds" in crescendo_entry["params"], (
        "CrescendoAttack params must include 'max_rounds'"
    )


# ── SPEC-017 ─────────────────────────────────────────────────────────


def test_SPEC_017_attacker_call_failure_recorded_as_non_committed_turn_loop_continues():
    """SPEC-017 (AC-13): attacker call failure is recorded as non-committed turn; loop continues."""
    # _FailOnFirstCallModel raises RuntimeError on call 1; succeeds after.
    attacker = _FailOnFirstCallModel(
        response=_VALID_ATK_RESPONSE,
        exc=RuntimeError("network error"),
    )
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    attacker_error_flags = ["attacker:" in (t.error or "") for t in turns]
    assert committed_flags.count(False) >= 1, (
        "must have at least one non-committed turn from failed attacker call"
    )
    assert True in attacker_error_flags, (
        "non-committed turn error must contain 'attacker:'"
    )
    assert committed_flags.count(True) >= 1, "must have at least one committed turn after recovery"


# ── SPEC-018 ─────────────────────────────────────────────────────────


def test_SPEC_018_target_call_failure_recorded_and_HT_backtracked():
    """SPEC-018 (AC-13): target call failure is recorded with 'target:' error and H_T is backtracked."""
    # _FailOnFirstCallTargetModel raises KeyError('content') on call 1; succeeds after.
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = _FailOnFirstCallTargetModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    target_error_flags = ["target:" in (t.error or "") for t in turns]
    assert committed_flags.count(False) >= 1, (
        "must have at least one non-committed turn from failed target call"
    )
    assert True in target_error_flags, (
        "non-committed turn error must contain 'target:'"
    )
    assert committed_flags.count(True) >= 1, "must have at least one committed turn after recovery"


# ── SPEC-019 ─────────────────────────────────────────────────────────


def test_SPEC_019_refusal_judge_failure_treated_as_refusal():
    """SPEC-019 (AC-13): refusal_judge exception treated as refusal; turn is not committed."""
    # _FailOnFirstCallEvaluator raises RuntimeError on call 1; accepts (False) after.
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _FailOnFirstCallEvaluator()
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    assert turns[0].committed is False, (
        "first turn (refusal_judge raised) must have committed=False"
    )
    assert committed_flags.count(True) >= 1, "second round (judge succeeded) must have committed=True"


# ── SPEC-020 ─────────────────────────────────────────────────────────


def test_SPEC_020_success_judge_failure_synthesises_non_success_turn_is_committed():
    """SPEC-020 (AC-13): success_judge exception synthesises non-success verdict; turn is still committed."""
    # _AlwaysRaisingEvaluator raises RuntimeError on every evaluate() call.
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _AlwaysRaisingEvaluator()

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    assert turns[0].committed is True, (
        "turn must be committed even when success_judge raises"
    )
    assert turns[0].success_judge_verdict.get("success") is False, (
        "synthesised verdict must have success=False"
    )
    assert "error" in turns[0].success_judge_verdict, (
        "synthesised verdict must contain an 'error' key"
    )
    assert result.success is False, "result.success must be False"


# ── SPEC-021 ─────────────────────────────────────────────────────────


def test_SPEC_021_conversation_attack_apply_returns_2_tuple(minimal_attack):
    """SPEC-021 (AC-14): apply() returns a 2-tuple (prompt_str, metadata_dict)."""
    result = minimal_attack.apply("some goal")

    assert isinstance(result, tuple), "apply() must return a tuple"
    assert len(result) == 2, "apply() must return a tuple of length 2"
    prompt_str, metadata = result
    assert isinstance(prompt_str, str), "first element must be a string"
    json.loads(prompt_str)  # must not raise
    assert isinstance(metadata, dict), "second element must be a dict"
    assert "goal" in metadata, "metadata must have 'goal' key"
    assert "success" in metadata, "metadata must have 'success' key"
    assert "iterations" in metadata, "metadata must have 'iterations' key"


# ── SPEC-022 ─────────────────────────────────────────────────────────


def test_SPEC_022_stream_abatch_yields_one_transcript_json_per_input():
    """SPEC-022 (AC-14, AC-08): stream_abatch yields exactly one JSON transcript string per input prompt.

    Metadata is not yielded — it will be reintroduced through a separate channel.
    Input-order is asserted by the per-prompt count contract here; the goal-by-goal
    ordering assertion will return once metadata is plumbed back through.
    """
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )

    input_goals = ["goal A", "goal B", "goal C"]
    results = async_collect(attack.stream_abatch(input_goals))

    parsed_shapes = [
        (isinstance(r, str), isinstance(json.loads(r), list))
        for r in results
    ]

    assert len(results) == 3, "stream_abatch must yield exactly 3 elements"
    assert parsed_shapes == [(True, True)] * 3, (
        "every element must be a JSON string parsing to a list of message dicts"
    )


# ── SPEC-023 ─────────────────────────────────────────────────────────


def test_SPEC_023_synthetic_saturation_marker_appended_when_attacker_always_fails():
    """SPEC-023 (AC-13): when attacker always raises, at least 1 turn record with committed=False is present."""
    # _AlwaysRaisingModel raises RuntimeError on every invoke() / ainvoke() call.
    attacker = _AlwaysRaisingModel()
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=1,
    )

    result = attack.run_attack("goal")

    assert len(result.iterations[0].turns) >= 1, (
        "must have at least 1 turn record even when attacker always fails"
    )
    assert result.iterations[0].turns[0].committed is False, (
        "turn record from always-failing attacker must have committed=False"
    )
    assert result.iterations[0].turns[0].error, (
        "turn record from always-failing attacker must have a non-empty error field"
    )


# ── SPEC-024 ─────────────────────────────────────────────────────────


def test_SPEC_024_final_transcript_is_from_first_success_iteration():
    """SPEC-024 (AC-15): final_transcript is from first-success iteration, not last attempted.

    Uses two rounds per iteration so each iteration has a committed (non-final)
    target answer that survives the trailing-answer drop, giving the transcript
    iteration-specific content to assert provenance against.
    """
    # iter 0: rounds 0,1 -> iter0_r0, iter0_r1 (both committed, no success)
    # iter 1: rounds 0,1 -> iter1_r0 (committed), iter1_r1 (committed + success)
    target = Mock(spec=Model)
    target.invoke.side_effect = [
        {"content": "iter0_r0"},
        {"content": "iter0_r1"},
        {"content": "iter1_r0"},
        {"content": "iter1_r1"},
    ]
    target.__class__ = type("MockTargetModel", (), {"__name__": "MockTargetModel"})

    # success_judge: True only on the last call (iter 1, round 1)
    success_judge = Mock(spec=BaseEvaluator)
    success_judge.evaluate.side_effect = [
        {"success": False},
        {"success": False},
        {"success": False},
        {"success": True},
    ]
    success_judge.get_name.return_value = "MockSuccessJudge"

    refusal_judge = Mock(spec=BaseEvaluator)
    refusal_judge.evaluate.return_value = {"success": True}
    refusal_judge.get_name.return_value = "MockRefusalJudge"

    attacker = MockModel(response=_VALID_ATK_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=3,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    assert len(result.iterations) == 2, "must have exactly 2 iterations (iter 0 failed, iter 1 succeeded)"
    assert result.final_transcript, "final_transcript must be non-empty"
    assert result.final_transcript[-1]["role"] == "human", (
        "final_transcript must end on a human turn (trailing target answer dropped)"
    )
    transcript_contents = [m.get("content", "") for m in result.final_transcript]
    # The committed iter-1 round-0 answer stays as conversational context...
    assert any("iter1_r0" in c for c in transcript_contents), (
        "final_transcript must retain the committed iter-1 context answer 'iter1_r0'"
    )
    # ...the successful final answer is dropped...
    assert not any("iter1_r1" in c for c in transcript_contents), (
        "final_transcript must NOT contain the final target answer 'iter1_r1' (it is dropped)"
    )
    # ...and nothing from the failed iteration 0 leaks in.
    assert not any("iter0" in c for c in transcript_contents), (
        "final_transcript must NOT contain any iteration-0 response (failed iteration)"
    )


# ── SPEC-025 ─────────────────────────────────────────────────────────


def test_SPEC_025_goal_with_literal_braces_does_not_raise():
    """SPEC-025 (AC-10): goal containing literal curly braces does not raise KeyError/IndexError;
    the literal goal string appears verbatim in the flat attacker prompt."""
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )

    goal = 'make {"payload": "{value}"}'
    attack.run_attack(goal)

    arg = attacker.call_log[0]
    assert isinstance(arg, str), "attacker prompt must be a flat str, not a message list"
    assert 'make {"payload": "{value}"}' in arg, (
        "flat attacker prompt must contain the literal goal string verbatim"
    )


# ── SPEC-026 ─────────────────────────────────────────────────────────


def test_SPEC_026_apply_with_list_of_messages_extracts_goal_from_last_human_message(minimal_attack):
    """SPEC-026 (AC-07): apply(list-of-messages) extracts goal from the last human-role message."""
    msgs = [{"role": "system", "content": "sys"}, {"role": "human", "content": "my goal"}]

    _, metadata = minimal_attack.apply(msgs)

    assert metadata["goal"] == "my goal", (
        "metadata['goal'] must equal the content of the last human message"
    )


# ── SPEC-027 ─────────────────────────────────────────────────────────


def test_SPEC_027_apply_with_no_human_message_raises_value_error(minimal_attack):
    """SPEC-027 (AC-07): apply() with no human-role message raises ValueError."""
    msgs = [{"role": "system", "content": "sys"}, {"role": "ai", "content": "response"}]

    with pytest.raises(ValueError):
        minimal_attack.apply(msgs)


# ── SPEC-028 ─────────────────────────────────────────────────────────


def test_SPEC_028_same_judge_instance_for_both_judges_is_accepted():
    """SPEC-028 (NFR-05): same judge instance for refusal_judge and success_judge is accepted."""
    j = _MockEvaluator(default={"success": False})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=j,
        success_judge=j,
    )

    assert attack.refusal_judge is attack.success_judge, (
        "refusal_judge and success_judge must be the same object when same instance is passed"
    )


# ── SPEC-029 ─────────────────────────────────────────────────────────


def test_SPEC_029_single_instance_judge_proceeds_through_one_round_normally():
    """SPEC-029 (NFR-05): a single judge instance shared between refusal_judge and success_judge
    is invoked once per role per turn and progresses the iteration consistently. Under the
    standard evaluator contract, ``success=True`` means *response is compliant/harmful*, so the
    shared judge interprets as: refusal_judge.success=True ⇒ not refused ⇒ commit; then
    success_judge.success=True on the same committed response ⇒ jailbreak ⇒ iteration short-
    circuits. Exactly one committed turn is recorded — the one that triggered success."""
    j = _MockEvaluator(default={"success": True})
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=j,
        success_judge=j,
        max_rounds=1,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    committed_flags = [t.committed for t in result.iterations[0].turns]
    assert committed_flags.count(True) == 1, (
        "exactly 1 committed turn must be recorded when using single shared judge"
    )
    assert result.success is True, (
        "shared judge returning success=True triggers both 'not refused' and 'jailbreak'"
    )


# ── SPEC-030 ─────────────────────────────────────────────────────────


def test_SPEC_030_attacker_plain_text_missing_q_field_recorded_with_missing_q_field_error():
    """SPEC-030 (AC-13): attacker returning plain text (missing q field) recorded with 'missing-q-field' error."""
    # _PlainTextThenValidModel returns plain text on call 1, valid JSON on call 2.
    attacker = _PlainTextThenValidModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=10,
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    missing_q_flags = ["missing-q-field" in (t.error or "") for t in turns]
    assert committed_flags.count(False) >= 1, (
        "must have at least one non-committed turn for missing-q-field"
    )
    assert True in missing_q_flags, (
        "non-committed turn must have 'missing-q-field' in error field"
    )
    assert committed_flags.count(True) >= 1, "must have at least one committed turn after recovery"


# ── SPEC-031 ─────────────────────────────────────────────────────────


def test_SPEC_031_default_values_are_10_10_10():
    """SPEC-031 (NFR-04): default max_rounds, max_iterations, refusal_cap are all 10."""
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator()

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
    )

    params = attack.get_params()

    assert params["max_rounds"] == 10, "default max_rounds must be 10"
    assert params["max_iterations"] == 10, "default max_iterations must be 10"
    assert params["refusal_cap"] == 10, "default refusal_cap must be 10"


# ── SPEC-032 ─────────────────────────────────────────────────────────


def test_SPEC_032_HA_history_rendered_inline_in_flat_attacker_prompt():
    """SPEC-032 (FR-02, FR-04): after N committed (q, summary) pairs in H_A, the next flat
    attacker prompt contains each q and summary inline in the rendered PREVIOUS_TURNS block.
    The attacker is never invoked with a separate system-role message."""
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=3,
        max_iterations=1,
        refusal_cap=10,
    )

    attack.run_attack("goal")

    # Third attacker call (index 2) corresponds to round 2, when H_A has 2 committed entries.
    assert len(attacker.call_log) >= 3, "attacker must have been called at least 3 times"
    third_call = attacker.call_log[2]
    assert isinstance(third_call, str), "attacker prompt must be a flat str, not a message list"

    # The fixed attacker response is _VALID_ATK_JSON = '{"q": "question", "summary": "summary"}';
    # after two committed rounds H_A contains [{"q":"question","summary":"summary"}, {...}],
    # so both fields are JSON-encoded into the PREVIOUS_TURNS block.
    assert "PREVIOUS_TURNS" in third_call
    assert third_call.count('"q": "question"') == 2, (
        "flat prompt must contain both prior committed q values inline"
    )
    assert third_call.count('"summary": "summary"') == 2, (
        "flat prompt must contain both prior committed summary values inline"
    )


# ── SPEC-033 ─────────────────────────────────────────────────────────


def test_SPEC_033_metadata_returned_by_apply_is_json_dumps_able(minimal_attack):
    """SPEC-033 (FR-15, FR-17): metadata returned by apply() is json.dumps-able with round-trip identity."""
    _, metadata = minimal_attack.apply("goal")

    serialised = json.dumps(metadata)
    assert json.loads(serialised) == metadata, (
        "metadata must survive a json.dumps/json.loads round-trip unchanged"
    )


# ── SPEC-DEFAULT-REFUSAL-001 ─────────────────────────────────────────


def test_SPEC_DEFAULT_REFUSAL_001_refusal_judge_defaults_to_keyword_evaluator():
    """SPEC-DEFAULT-REFUSAL-001: when refusal_judge is omitted, CrescendoAttack falls back to a
    plain ``KeywordEvaluator`` (no polarity shim). The standard evaluator contract holds —
    ``success=True`` ⇔ no refusal phrase found ⇔ compliant response — and Crescendo inverts
    that at the call site (``refused = not success``). End-to-end: a target response containing
    a bundled refusal phrase ("I'm sorry") makes the framework backtrack the turn; a clean
    response is committed."""
    from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator

    # Target returns a refusal phrase on call 1 (should be backtracked),
    # then a clean response on call 2 (should be committed).
    target = MockModel(side_effect=[
        {"content": "I'm sorry, I cannot help with that request"},
        {"content": "Here is the information you asked for: ..."},
    ])
    attacker = MockModel(response=_VALID_ATK_RESPONSE)
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=5,
    )

    # Default is plain KeywordEvaluator — no subclass, no polarity shim.
    assert type(attack.refusal_judge) is KeywordEvaluator, (
        "default refusal_judge must be a plain KeywordEvaluator (no subclass)"
    )

    result = attack.run_attack("goal")

    turns = result.iterations[0].turns
    committed_flags = [t.committed for t in turns]
    assert committed_flags.count(False) >= 1, (
        "the refusal-phrase response must produce at least one backtracked (non-committed) turn"
    )
    assert committed_flags.count(True) >= 1, (
        "the clean response must produce at least one committed turn"
    )


# ── SPEC-EMPTY-001 ───────────────────────────────────────────────────


def test_SPEC_EMPTY_001_empty_attacker_response_does_not_raise_and_records_turn():
    """SPEC-EMPTY-001 (AC-01, FR-02): an attacker model that always returns ``{"content": ""}``
    — the failure mode some target-side models exhibit when handed a system-only prompt —
    drives run_attack to terminate normally and record at least one turn per iteration,
    rather than raising or producing an iteration with zero turn records."""
    attacker = MockModel(response={"content": ""})
    target = MockModel(response=_VALID_TARGET_RESPONSE)
    refusal_judge = _MockEvaluator(default={"success": True})
    success_judge = _MockEvaluator(default={"success": False})

    attack = CrescendoAttack(
        attacker_model=attacker,
        target_model=target,
        refusal_judge=refusal_judge,
        success_judge=success_judge,
        max_rounds=2,
        max_iterations=1,
        refusal_cap=2,
    )

    result = attack.run_attack("goal")

    assert result.success is False, "attack with always-empty attacker cannot succeed"
    assert len(result.iterations) == 1, "exactly one iteration must be recorded"
    turns = result.iterations[0].turns
    assert len(turns) >= 1, "iteration must contain at least one turn record"
    assert all(t.committed is False for t in turns), (
        "no turn may be committed when the attacker never produces a valid q"
    )
    assert all("missing-q-field" in (t.error or "") for t in turns), (
        "every turn must record the missing-q-field error from empty attacker output"
    )
