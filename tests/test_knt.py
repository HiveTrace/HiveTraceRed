"""K / N / T knobs and the K-aware report."""

import inspect
import sys

import numpy as np
import pandas as pd
import pytest

from hivetracered.attacks import NoneAttack
from hivetracered.config import _force_judge_temperature
from hivetracered.models.base_model import TEMPERATURE_EPSILON
from hivetracered.pipeline.create_dataset import attack_repeats, stream_attack_prompts
from hivetracered.pipeline.model_responses import stream_model_responses
from hivetracered.report import (
    BOOTSTRAP_RESAMPLES, _attack_detailed_html, _bootstrap_means, _example_success,
    _paired_test_html, _per_attack_asr, asr_bound_method, asr_upper, attack_type_risk,
    bootstrap_lower_and_p, bootstrap_upper, calculate_metrics, clopper_pearson_upper,
    collapse_k_repeats, create_charts, bh_adjust, mcnemar_exact, mcnemar_vs_baseline,
    paired_bootstrap_vs_baseline, paired_test_vs_baseline,
)
from tests.conftest import MockModel, async_collect


def test_k_sends_each_prompt_k_times_and_error_rows_once():
    model = MockModel(side_effect=[{"content": "r0"}, {"content": "r1"}])
    attack_prompts = [{"prompt": "hello"}, {"prompt": "", "error": "attacker died"}]

    results = async_collect(stream_model_responses(model, attack_prompts, k=2))

    assert [(r["k_index"], r.get("response")) for r in results] == [(0, "r0"), (1, "r1"), (0, "")]
    assert len(model.call_log) == 2


def test_n_repeats_attack_per_example_with_distinct_n_index():
    attacks = {"NoneAttack": NoneAttack()}

    results = async_collect(stream_attack_prompts(attacks, ["q"], repeats={"NoneAttack": 2}))

    assert sorted(r["n_index"] for r in results) == [0, 1]


def test_attack_repeats_deterministic_attacks_run_once_unless_overridden(caplog):
    # NoneAttack / DANAttack are templates; PAIRAttack drives a model; TypoAttack uses random.
    configs = [
        "NoneAttack",
        {"name": "DANAttack", "N": 5},
        "PAIRAttack",
        {"name": "PAIRAttack", "N": 2},
        "TypoAttack",
    ]

    with caplog.at_level("WARNING"):
        repeats = attack_repeats(configs, global_n=3)

    assert repeats == {"NoneAttack": 1, "DANAttack": 5, "PAIRAttack": 2, "TypoAttack": 3}
    assert any("DANAttack" in m and "deterministic" in m for m in caplog.messages)


def test_attack_repeats_global_n_defaults_to_one():
    assert attack_repeats(["PAIRAttack"]) == {"PAIRAttack": 1}


def test_attacks_using_random_are_not_marked_deterministic():
    from hivetracered.pipeline.constants import ATTACK_CLASSES

    wrong = [
        name for name, info in ATTACK_CLASSES.items()
        if info["attack_class"].DETERMINISTIC
        and "random" in inspect.getsource(sys.modules[info["attack_class"].__module__])
    ]
    assert wrong == []


def test_circuit_breaker_counts_every_failed_request_including_repeats():
    # A dead key fails every request: 3 failures in a row trip the breaker even
    # when they are the K repeats of one prompt.
    err = {"content": "", "error": "boom"}
    model = MockModel(side_effect=[err, err, err])

    results = async_collect(stream_model_responses(
        model, [{"prompt": "a"}, {"prompt": "b"}], k=3, consecutive_failures=3,
    ))

    assert [r["error"] for r in results[:3]] == ["boom"] * 3
    assert all(r["error"].startswith("skipped_after_failures") for r in results[3:])
    assert len(model.call_log) == 3


@pytest.mark.parametrize(
    ("model_cls", "recommended"),
    [("OpenAIModel", 0.0), ("YandexGPTModel", TEMPERATURE_EPSILON)],
)
def test_judge_temperature_explicit_non_zero_is_kept_with_a_warning(model_cls, recommended, caplog):
    config = {"evaluation_model": {"model": model_cls, "params": {"temperature": 0.9}}}

    with caplog.at_level("WARNING"):
        _force_judge_temperature(config)

    assert config["evaluation_model"]["params"]["temperature"] == 0.9
    assert any("0.9" in m and str(recommended) in m for m in caplog.messages)


def test_judge_temperature_explicit_zero_is_kept_without_warning(caplog):
    config = {"evaluation_model": {"model": "OpenAIModel", "params": {"temperature": 0.0}}}

    with caplog.at_level("WARNING"):
        _force_judge_temperature(config)

    assert config["evaluation_model"]["params"]["temperature"] == 0.0
    assert not any("evaluation_model temperature" in m for m in caplog.messages)


def _repeat_rows(successes, base_prompt="p"):
    return pd.DataFrame([
        {"attack_name": "A", "base_prompt": base_prompt, "n_index": 0, "k_index": i, "success": s}
        for i, s in enumerate(successes)
    ])


@pytest.mark.parametrize(
    ("successes", "expected"),
    [
        ([True], 1.0),                   # K=1: the single run's verdict
        ([False], 0.0),
        ([True, True, False], 2 / 3),
        ([True, False], 0.5),
        ([True, True, False, False, False], 0.4),
    ],
)
def test_k_repeats_collapse_to_mean_success(successes, expected):
    out = collapse_k_repeats(_repeat_rows(successes))

    assert len(out) == 1
    assert out["success"].iloc[0] == pytest.approx(expected)
    assert out["K"].iloc[0] == len(successes)
    assert "k_index" not in out.columns


def test_collapse_keeps_units_separate():
    df = pd.concat([_repeat_rows([True, True]), _repeat_rows([False, False], "q")], ignore_index=True)

    out = collapse_k_repeats(df)

    assert out.set_index("base_prompt")["success"].to_dict() == {"p": True, "q": False}


def test_collapse_keeps_duplicate_examples_and_short_units():
    # Two examples with the same text at K=1 stay two rows; a unit with fewer
    # repeats than K (stage-1 error) is judged on its own rows.
    df = pd.concat([
        _repeat_rows([True]), _repeat_rows([False]),
        _repeat_rows([True, False, False], "q"), _repeat_rows([True], "r"),
    ], ignore_index=True)

    out = collapse_k_repeats(df)

    assert out["success"].tolist() == pytest.approx([1.0, 0.0, 1 / 3, 1.0])
    assert out["K"].iloc[0] == 3


def test_collapse_takes_first_whole_row_without_error():
    df = _repeat_rows([False, True, True])
    df["error"] = ["timeout", None, None]
    df["response"] = [None, "second", "third"]

    out = collapse_k_repeats(df)

    assert out["response"].iloc[0] == "second"
    assert pd.isna(out["error"].iloc[0])
    assert bool(out["success"].iloc[0]) is True


def test_collapse_falls_back_to_repeat_zero_when_all_failed():
    df = _repeat_rows([False, False])
    df["error"] = ["timeout", "refused"]

    out = collapse_k_repeats(df)

    assert out["error"].iloc[0] == "timeout"


@pytest.mark.parametrize("block", ["K: 0", "N: -1", "attacks:\n  - {name: PAIRAttack, N: 0}"])
def test_load_config_rejects_repeats_below_one(tmp_path, block):
    from hivetracered.config import load_config

    cfg = tmp_path / "c.yaml"
    cfg.write_text(block + "\n")

    with pytest.raises(ValueError, match=">= 1"):
        load_config(str(cfg))


def test_load_config_defaults_omitted_judge_temperature(tmp_path):
    from hivetracered.config import load_config

    cfg = tmp_path / "c.yaml"
    cfg.write_text("evaluation_model:\n  model: OpenAIModel\n  name: gpt\n")

    assert load_config(str(cfg))["evaluation_model"]["params"]["temperature"] == 0.0


def test_load_config_keeps_explicit_judge_temperature(tmp_path, caplog):
    from hivetracered.config import load_config

    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "evaluation_model:\n  model: OpenAIModel\n  name: gpt\n  params:\n    temperature: 0.7\n"
    )

    with caplog.at_level("WARNING"):
        loaded = load_config(str(cfg))

    assert loaded["evaluation_model"]["params"]["temperature"] == 0.7
    assert any("0.7" in m for m in caplog.messages)


def test_clopper_pearson_upper():
    # Reference: largest p with P(X <= x | n, p) >= 0.05, bisection on the
    # binomial CDF (equals scipy.stats.beta.ppf(0.95, x + 1, n - x)).
    assert clopper_pearson_upper(0, 30) == pytest.approx(9.503, abs=0.01)
    assert clopper_pearson_upper(50, 100) == pytest.approx(58.638, abs=0.01)
    assert clopper_pearson_upper(2, 10) == pytest.approx(50.690, abs=0.01)
    assert 50.690 < clopper_pearson_upper(2.5, 10) < 60.662  # fractional successes interpolate
    assert clopper_pearson_upper(30, 30) == 100.0
    assert clopper_pearson_upper(0, 0) == 0.0


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert mcnemar_exact(8, 2) == pytest.approx(0.109, abs=0.001)


def test_mcnemar_vs_baseline_pairs_by_example():
    prompts = [f"p{i}" for i in range(12)]
    rows = [{"attack_name": "NoneAttack", "base_prompt": p, "success": False} for p in prompts]
    rows += [{"attack_name": "DAN", "base_prompt": p, "success": i < 10} for i, p in enumerate(prompts)]
    rows += [{"attack_name": "Noop", "base_prompt": p, "success": False} for p in prompts]
    rows += [{"attack_name": "Partial", "base_prompt": p, "success": 2 / 3 if i == 0 else 1 / 3}
             for i, p in enumerate(prompts)]  # K-averaged: only p0 counts as success

    table = mcnemar_vs_baseline(pd.DataFrame(rows)).set_index("attack_name")

    assert table.loc["DAN", "b (0→1)"] == 10 and table.loc["DAN", "c (1→0)"] == 0
    assert table.loc["DAN", "significant"]
    assert table.loc["DAN", "Δ (pp)"] == pytest.approx(10 / 12 * 100)
    assert table.loc["Noop", "p-value"] == 1.0 and not table.loc["Noop", "significant"]
    assert table.loc["Partial", "b (0→1)"] == 1
    assert "NoneAttack" not in table.index


def test_mcnemar_without_baseline_is_empty():
    df = pd.DataFrame([{"attack_name": "DAN", "base_prompt": "p", "success": True}])
    assert mcnemar_vs_baseline(df).empty


def test_upper_bound_counts_examples_not_repeats():
    # 4 examples x N=3 repeats: the per-attack bound must use n=4, not n=12.
    df = pd.DataFrame([
        {
            "attack_type": "iterative", "attack_name": "PAIR",
            "base_prompt": f"p{i}", "n_index": n, "success": float(i == 0),
            "is_blocked": False, "error": "",
        }
        for i in range(4) for n in range(3)
    ])

    assert _example_success(df) == (1.0, 4)
    assert "success_rate_upper" not in calculate_metrics(df)
    assert "≤{:.1f}%".format(clopper_pearson_upper(1, 4)) in _attack_detailed_html(df)


@pytest.mark.parametrize("pvalues, expected", [
    ([], []),
    ([0.04], [0.04]),
    ([0.01, 0.04, 0.03], [0.03, 0.04, 0.04]),
    ([0.5, 0.6, 0.1, 0.001], [0.6, 0.6, 0.2, 0.004]),
    ([1.0, 0.0, 0.02, 0.02], [1.0, 0.0, 0.08 / 3, 0.08 / 3]),
])
def test_bh_adjust(pvalues, expected):
    assert bh_adjust(pvalues) == pytest.approx(expected)


@pytest.mark.parametrize("compare", [mcnemar_vs_baseline, paired_bootstrap_vs_baseline])
def test_paired_comparisons_apply_bh_across_attacks(compare, monkeypatch):
    # These p-values reject all three with BH, but only the first with Holm.
    pvalues = iter([0.01, 0.04, 0.03])
    monkeypatch.setattr("hivetracered.report.mcnemar_exact", lambda b, c: next(pvalues))
    monkeypatch.setattr("hivetracered.report.bootstrap_lower_and_p",
                        lambda values, **kwargs: (0.0, next(pvalues)))
    df = pd.DataFrame([
        {"attack_name": name, "base_prompt": "p", "success": False}
        for name in ["NoneAttack", "A", "B", "C"]
    ])
    table = compare(df).set_index("attack_name").loc[["A", "B", "C"]]
    assert table["p (BH)"].tolist() == pytest.approx([0.03, 0.04, 0.04])
    assert table["significant"].all()


def test_content_charts_use_per_request_bool_not_k_mean():
    raw = _repeat_rows([True, False, False])
    raw["attack_type"] = "persona"
    raw["is_blocked"] = False
    raw["did_answer"] = [True, False, False]
    raw["response"] = ["jailbroken", "no", "no"]
    raw["response_length"] = [10, 2, 2]
    collapsed = collapse_k_repeats(raw)

    charts = create_charts(collapsed, per_request=raw)

    for key in ("fig_length_html", "fig_answer_html"):
        html = charts[key]
        assert '"x":["Success"]' in html or "Success" in html
        assert "Fail" in html
        assert '"x":[0.333' not in html


# ── bootstrap over examples ─────────────────────────────────────────


def test_bootstrap_means_is_deterministic_and_resamples_examples():
    values = np.linspace(0, 1, 40)

    draws = _bootstrap_means(values)

    assert draws.shape == (BOOTSTRAP_RESAMPLES,)
    assert np.array_equal(draws, _bootstrap_means(values))  # same seed, same report
    assert draws.min() > 0 and draws.max() < 1
    assert _bootstrap_means(values).mean() == pytest.approx(values.mean(), abs=0.01)


def test_bootstrap_upper_matches_the_normal_approximation_on_a_large_sample():
    # With n = 200 the percentile bootstrap should land on mean + 1.645 * SE.
    values = np.random.default_rng(0).beta(2, 5, 200)
    expected = (values.mean() + 1.645 * values.std(ddof=1) / np.sqrt(values.size)) * 100

    assert bootstrap_upper(values) == pytest.approx(expected, abs=0.5)
    assert bootstrap_upper(values) > values.mean() * 100


def test_bootstrap_upper_beats_clopper_pearson_on_fractional_successes():
    # The whole point of the switch: the exact binomial bound treats a 0.4 as a
    # coin flip and over-states the variance.
    values = np.random.default_rng(0).beta(2, 5, 200)

    assert bootstrap_upper(values) < clopper_pearson_upper(values.sum(), values.size)


@pytest.mark.parametrize(
    ("values", "method"),
    [
        ([0.0, 1.0, 1.0, 0.0], "Clopper-Pearson"),   # K = N = 1: plain trials
        ([0.4, 0.6, 0.0, 1.0], "bootstrap"),         # repeats collapsed to fractions
        ([0.4, 0.4, 0.4], "Clopper-Pearson"),        # degenerate: bootstrap would give U = 40%
        ([0.0, 0.0, 0.0], "Clopper-Pearson"),        # all zero: bootstrap would claim "at most 0%"
    ],
)
def test_asr_upper_picks_the_method_the_data_supports(values, method):
    upper, chosen = asr_upper(np.array(values))

    assert chosen == method
    assert upper >= np.mean(values) * 100


def test_asr_upper_never_reports_zero_risk_from_an_all_zero_run():
    assert asr_upper(np.zeros(30))[0] == pytest.approx(clopper_pearson_upper(0, 30))


def test_bootstrap_lower_and_p_is_one_sided():
    # A uniform +40pp effect: the lower bound sits at the effect, p hits the floor.
    low, p = bootstrap_lower_and_p(np.full(50, 0.4))
    assert low == pytest.approx(40.0) and p == 0.0

    # No effect at all: p = 1, bound at zero (rounding noise must not leak).
    low, p = bootstrap_lower_and_p(np.zeros(50))
    assert low == pytest.approx(0.0) and p == 1.0

    # An attack that *lowers* ASR is never evidence for H1.
    low, p = bootstrap_lower_and_p(np.full(50, -0.4))
    assert low < 0 and p == 1.0


# ── paired test: McNemar at K=N=1, bootstrap once there are repeats ──


def _paired_df(base_success, attack_success, n=40, attack="Sneaky"):
    rows = []
    for i in range(n):
        for name, value in (("NoneAttack", base_success), (attack, attack_success)):
            rows.append({
                "attack_type": "t", "attack_name": name,
                "base_prompt": f"p{i}", "success": value,
            })
    return pd.DataFrame(rows)


def test_paired_test_uses_mcnemar_on_binary_outcomes():
    table, method = paired_test_vs_baseline(_paired_df(0.0, 1.0))

    assert method == "exact McNemar"
    assert "b (0→1)" in table.columns and table["significant"].all()


def test_paired_bootstrap_sees_the_effect_mcnemar_binarisation_hides():
    # Every example fails 2 of its 5 repeats to the attack and none to the
    # baseline. McNemar has to call 0.4 a failure, so it sees nothing.
    df = _paired_df(0.0, 0.4)

    table, method = paired_test_vs_baseline(df)
    row = table.set_index("attack_name").loc["Sneaky"]

    assert method == "paired bootstrap"
    assert row["Δ (pp)"] == pytest.approx(40.0)
    assert row["Δ 95% lower (pp)"] == pytest.approx(40.0)
    assert row["p (BH)"] == 0.0 and row["significant"]
    assert mcnemar_vs_baseline(df).set_index("attack_name").loc["Sneaky", "p-value"] == 1.0


def test_paired_bootstrap_does_not_flag_an_attack_that_lowers_asr():
    table = paired_bootstrap_vs_baseline(_paired_df(0.6, 0.2)).set_index("attack_name")

    assert table.loc["Sneaky", "Δ (pp)"] == pytest.approx(-40.0)
    assert not table.loc["Sneaky", "significant"]


def test_paired_test_html_reports_the_method_and_the_bootstrap_p_floor():
    html, title, note = _paired_test_html(_paired_df(0.0, 0.4))

    assert "paired bootstrap" in title
    assert f"&lt;{1 / BOOTSTRAP_RESAMPLES:g}" in html  # a Monte-Carlo zero, not p = 0
    assert "Δ 95% lower (pp)" in html and "one-sided" in note

    html, title, _ = _paired_test_html(_paired_df(0.0, 1.0))
    assert "exact McNemar" in title and "b (0→1)" in html


def test_paired_test_without_baseline_is_empty():
    df = _paired_df(0.0, 0.4).query("attack_name != 'NoneAttack'")

    table, _ = paired_test_vs_baseline(df)

    assert table.empty and _paired_test_html(df)[0] == ""


# ── per-type plug-in risk ───────────────────────────────────────────


def test_attack_type_risk_is_the_plug_in_over_the_attacks_of_the_type():
    # Two attacks of one type break half the repeats of every example:
    # one attempt each -> 1 - 0.5 * 0.5 = 75%.
    rows = [
        {"attack_type": "encoding", "attack_name": name, "base_prompt": f"p{i}", "success": 0.5}
        for i in range(20) for name in ("base64", "rot13")
    ]
    rows += [
        {"attack_type": "persona", "attack_name": "DAN", "base_prompt": f"p{i}", "success": 0.0}
        for i in range(20)
    ]

    table = attack_type_risk(pd.DataFrame(rows)).set_index("attack_type")

    assert table.loc["encoding", "One-attempt Risk"] == pytest.approx(75.0)
    assert table.loc["encoding", "Attacks"] == 2 and table.loc["encoding", "Examples"] == 20
    assert table.loc["persona", "One-attempt Risk"] == 0.0
    assert table.loc["persona", "upper"] > 0  # all-zero run is not "no risk"


def test_attack_type_risk_ignores_errored_rows_and_empty_frames():
    rows = [
        {"attack_type": "t", "attack_name": "A", "base_prompt": f"p{i}",
         "success": 1.0 if i else 0.0, "error": "" if i else "boom"}
        for i in range(3)
    ]

    table = attack_type_risk(pd.DataFrame(rows))

    assert table.loc[0, "Examples"] == 2 and table.loc[0, "One-attempt Risk"] == 100.0
    assert attack_type_risk(pd.DataFrame()).empty


# ── wiring ──────────────────────────────────────────────────────────


def test_per_attack_asr_bound_follows_the_repeat_structure():
    binary = _paired_df(0.0, 1.0)
    fractional = _paired_df(0.0, 0.4)
    # Examples must differ for the bootstrap to have anything to resample; a run
    # where every example scores the same 0.4 deliberately falls back to exact.
    varied = fractional.copy()
    varied.loc[varied["attack_name"] == "Sneaky", "success"] = [
        0.2 if i % 2 else 0.6 for i in range(40)
    ]

    assert set(_per_attack_asr(binary)["upper method"]) == {"Clopper-Pearson"}
    assert asr_bound_method(binary) == "Clopper-Pearson"
    assert asr_bound_method(fractional) == "bootstrap"
    assert _per_attack_asr(fractional).set_index("attack_name").loc[
        "Sneaky", "upper method"] == "Clopper-Pearson"

    sneaky = _per_attack_asr(varied).set_index("attack_name").loc["Sneaky"]
    assert sneaky["upper method"] == "bootstrap"
    assert 40.0 < sneaky["upper"] < clopper_pearson_upper(16.0, 40)
