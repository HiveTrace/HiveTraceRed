"""Regressions: an errored, unjudged or duplicated example must never be
counted as a failed attack, dropped, or merged with another example."""

import asyncio

import pandas as pd
import pytest

from hivetracered import report, runner
from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
from hivetracered.pipeline.create_dataset import stream_attack_prompts
from hivetracered.setup import DatasetSpec, load_records


def _rows(attacks, examples, **extra):
    return [
        dict(attack_name=a, attack_type="test", base_prompt=str(i), base_prompt_id=i,
             success=False, is_blocked=False, error="", **extra)
        for a in attacks for i in range(examples)
    ]


def test_upper_bound_is_not_zero_when_every_repeat_failed():
    # 30 examples x K=2, no success at all: the bootstrap is degenerate here,
    # "at most 0%" would be a false guarantee. Exact bound for 0/30 is 9.5%.
    rows = [dict(r, k_index=k) for r in _rows(["A"], 30) for k in range(2)]
    frame = report.collapse_k_repeats(report._prepare_frame(pd.DataFrame(rows)))

    stats = report._per_attack_asr(frame).set_index("attack_name")

    assert stats.loc["A", "upper"] == pytest.approx(9.503, abs=1e-3)
    assert stats.loc["A", "upper method"] == "Clopper-Pearson"


def test_mcnemar_drops_pair_whose_baseline_request_failed():
    rows = _rows(["NoneAttack", "A"], 2)
    for r in rows:
        r["success"] = r["attack_name"] == "A"
    rows[1]["error"] = "timeout"  # NoneAttack, example 1

    table = report.mcnemar_vs_baseline(pd.DataFrame(rows)).set_index("attack_name")

    assert table.loc["A", "n pairs"] == 1
    assert table.loc["A", "b (0→1)"] == 1


def test_paired_bootstrap_drops_pair_whose_baseline_request_failed():
    rows = [dict(r, k_index=k) for r in _rows(["NoneAttack", "A"], 3) for k in range(2)]
    for r in rows:
        r["success"] = r["attack_name"] == "A" and r["k_index"] == 0
        if r["attack_name"] == "NoneAttack" and r["base_prompt_id"] == 2:
            r["error"] = "timeout"
    frame = report.collapse_k_repeats(report._prepare_frame(pd.DataFrame(rows)))

    table, method = report.paired_test_vs_baseline(frame)

    assert method == "paired bootstrap"
    assert table.set_index("attack_name").loc["A", "n pairs"] == 2


@pytest.mark.parametrize("evaluation", [
    {"evaluation_error": "timeout"},
    {"error": "judge returned garbage"},
    {"raw_evaluation": {"error": "429"}},
    "{'evaluation_error': 'timeout'}",  # as read back from a CSV
])
def test_judge_error_is_not_a_failed_attack(evaluation):
    rows = _rows(["A"], 2)
    rows[0].update(success=True, evaluation={})
    rows[1].update(success=False, evaluation=evaluation)
    frame = report._prepare_frame(pd.DataFrame(rows))

    metrics = report.calculate_metrics(frame)

    assert metrics["success_rate"] == pytest.approx(100.0)
    assert metrics["error_count"] == 1
    assert report._per_attack_asr(frame).iloc[0]["examples"] == 1


def test_row_without_verdict_is_not_a_failed_attack():
    rows = _rows(["A"], 2)
    rows[0]["success"] = True
    rows[1]["success"] = None
    frame = report._prepare_frame(pd.DataFrame(rows))

    assert report.calculate_metrics(frame)["success_rate"] == pytest.approx(100.0)


def test_k_repeat_with_judge_error_is_left_out_of_the_fraction():
    rows = [dict(r, k_index=k, evaluation={}) for r in _rows(["A"], 1) for k in range(3)]
    rows[0]["success"] = True
    rows[1]["success"] = True
    rows[2]["evaluation"] = {"evaluation_error": "timeout"}

    frame = report.collapse_k_repeats(report._prepare_frame(pd.DataFrame(rows)))

    assert len(frame) == 1
    assert frame.iloc[0]["success"] == pytest.approx(1.0)  # 2 of 2 judged, not 2 of 3


def test_all_requests_failed_gives_unknown_rate_not_zero():
    rows = _rows(["A"], 2, )
    for r in rows:
        r["error"] = "timeout"

    metrics = report.calculate_metrics(report._prepare_frame(pd.DataFrame(rows)))

    assert pd.isna(metrics["success_rate"])
    assert metrics["error_rate"] == pytest.approx(100.0)
    assert report._fmt_rate(metrics["success_rate"]) == "n/a"


def test_examples_with_identical_text_stay_separate_observations():
    rows = _rows(["A"], 2)
    for r in rows:
        r["base_prompt"] = "same text"
    rows[1]["success"] = True

    stats = report._per_attack_asr(report._prepare_frame(pd.DataFrame(rows)))

    assert stats.iloc[0]["examples"] == 2
    assert stats.iloc[0][report.SUCCESS_RATE] == pytest.approx(50.0)


def test_result_files_without_example_id_fall_back_to_text():
    rows = _rows(["A"], 2)
    for r in rows:
        del r["base_prompt_id"]

    assert report._per_attack_asr(pd.DataFrame(rows)).iloc[0]["examples"] == 2


def test_stage3_scores_the_response_text_and_skips_blocked_rows():
    # The refusal keyword sits in the *prompt*; the response has none.
    spec = DatasetSpec("test", ["I cannot"], KeywordEvaluator(keywords=["I cannot"]))
    responses = [
        dict(base_prompt="I cannot", response="answer", is_blocked=False),
        dict(base_prompt="hello", response="", is_blocked=True),
    ]

    out = asyncio.run(runner._evaluate_dataset(spec, responses))

    assert [r["success"] for r in out] == [True, False]


def test_empty_csv_error_cell_is_not_an_error(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("response,error\nanswer,\n,failed\n")

    records = load_records(str(path))

    assert not records[0]["error"]
    assert records[1]["error"] == "failed"


def test_attack_failing_mid_stream_yields_one_row_per_prompt():
    from hivetracered.attacks.base_attack import BaseAttack

    class _BreaksOnSecond(BaseAttack):
        def apply(self, prompt):
            return prompt

        async def stream_abatch(self, prompts):
            yield prompts[0]
            raise RuntimeError("attacker model died")

        def get_name(self):
            return "NoneAttack"

        def get_description(self):
            return ""

    attack = _BreaksOnSecond()
    attack.__class__.__name__ = "NoneAttack"

    async def _collect():
        return [r async for r in stream_attack_prompts({"NoneAttack": attack}, ["p0", "p1", "p2"])]

    rows = asyncio.run(_collect())

    assert [r["base_prompt_id"] for r in rows] == [0, 1, 2]
    assert [bool(r["error"]) for r in rows] == [False, True, True]


def test_vulnerable_prompt_counts_keep_identical_texts_apart():
    rows = _rows(["A"], 2)
    for r in rows:
        r.update(base_prompt="same text", success=True)
    frame = report._prepare_frame(pd.DataFrame(rows))

    assert report._vulnerable_prompts(frame)[:2] == (2, 2)
    assert report._per_type_stats(frame)[0]["Total Unique Prompts"] == 2


def test_collapse_keeps_each_fraction_with_its_own_example():
    # Example 0: first repeat errored, second succeeded. Example 1: failed twice.
    # Rows ordered by repeat, so the healthy row of example 0 comes *after*
    # example 1's first row.
    rows = [dict(r, k_index=k) for k in range(2) for r in _rows(["A"], 2)]
    rows[0]["error"] = "timeout"   # example 0, k=0
    rows[2]["success"] = True      # example 0, k=1

    frame = report.collapse_k_repeats(report._prepare_frame(pd.DataFrame(rows)))

    assert frame.set_index("base_prompt_id")["success"].to_dict() == {0: 1.0, 1: 0.0}


def test_stream_evaluation_marks_rows_the_evaluator_never_scored():
    from hivetracered.pipeline.evaluation import stream_evaluated_responses

    class _StopsEarly(KeywordEvaluator):
        async def stream_abatch(self, prompts, responses):
            yield {"success": True}

    responses = [dict(base_prompt=str(i), response="answer", is_blocked=False) for i in range(3)]
    responses.append(dict(base_prompt="3", response="", is_blocked=True))

    async def _collect():
        return [r async for r in stream_evaluated_responses(_StopsEarly(keywords=["x"]), responses)]

    rows = asyncio.run(_collect())

    assert [r["base_prompt"] for r in rows] == ["0", "1", "2", "3"]
    assert [bool(r["evaluation_error"]) for r in rows] == [False, True, True, False]


def test_content_charts_leave_errored_rows_out():
    rows = _rows(["A"], 2)
    rows[0].update(success=True, response="long answer", did_answer="yes")
    rows[1].update(error="timeout", response="", did_answer="unknown")
    frame = report._prepare_frame(pd.DataFrame(rows))

    length_html, _ = report._build_length_charts_html(frame)
    answer_html = report._build_answer_html(frame)

    assert "Fail" not in length_html
    assert "unknown" not in answer_html
