"""K / N / T knobs and the K-aware report."""

import inspect
import sys

import pytest

from hivetracered.attacks import NoneAttack
from hivetracered.config import _force_judge_temperature
from hivetracered.models.base_model import TEMPERATURE_EPSILON
from hivetracered.pipeline.create_dataset import attack_repeats, stream_attack_prompts
from hivetracered.pipeline.model_responses import stream_model_responses
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
