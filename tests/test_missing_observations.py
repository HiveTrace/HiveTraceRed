"""Regressions: an errored, unjudged or duplicated example must never be
counted as a failed attack, dropped, or merged with another example."""

import asyncio

from hivetracered import runner
from hivetracered.evaluators.keyword_evaluator import KeywordEvaluator
from hivetracered.pipeline.create_dataset import stream_attack_prompts
from hivetracered.setup import DatasetSpec, load_records


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
