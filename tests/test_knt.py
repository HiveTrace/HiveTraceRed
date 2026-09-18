"""K / N / T knobs and the K-aware report."""

import pytest

from hivetracered.config import _force_judge_temperature
from hivetracered.models.base_model import TEMPERATURE_EPSILON


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
