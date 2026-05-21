"""Unit tests for the create_dataset pipeline module.

Covers attack-config parsing, prompt extraction/creation, attack construction
from configs, attack setup, and the streaming attack-prompt generator.
"""

from __future__ import annotations

import pytest

from hivetracered.attacks.composed_attack import ComposedAttack
from hivetracered.attacks.template_attack import TemplateAttack
from hivetracered.pipeline.create_dataset import (
    build_attack_from_config,
    create_prompt,
    extract_prompt_text,
    setup_attacks,
    stream_attack,
)
from tests.conftest import async_collect


# ── Fixtures local to this file ─────────────────────────────────────


@pytest.fixture
def template_attack_cls(monkeypatch):
    """Register a tiny TemplateAttack subclass into ATTACK_CLASSES.

    Lets us drive build_attack_from_config / stream_attack against a
    deterministic attack without invoking real registered classes.
    """
    class _BangAttack(TemplateAttack):
        def __init__(self, suffix: str = "!"):
            super().__init__(template=f"{{prompt}}{suffix}")
            self.suffix = suffix

    # Inject into the live registry view used by create_dataset
    from hivetracered.registry import Registry
    Registry._attacks["_BangAttack"] = {"class": _BangAttack, "category": "test"}
    yield _BangAttack
    Registry._attacks.pop("_BangAttack", None)


# ── extract_prompt_text ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    ["prompt", "Prompt", "text", "Text", "question", "Question"],
)
def test_extract_prompt_text_dict_returns_value_for_each_supported_key(key):
    result = extract_prompt_text({key: "the-value"})

    assert result == "the-value"


def test_extract_prompt_text_dict_missing_known_key_raises_value_error():
    with pytest.raises(ValueError, match=r"No prompt field found"):
        extract_prompt_text({"unrelated": "x"})


def test_extract_prompt_text_unsupported_type_raises_value_error():
    with pytest.raises(ValueError, match=r"Unsupported base_prompt type"):
        extract_prompt_text(42)


# ── create_prompt ───────────────────────────────────────────────────


def test_create_prompt_with_system_prompt_returns_two_message_list():
    result = create_prompt("hello", system_prompt="be nice")

    assert isinstance(result, list)
    assert len(result) == 2  # = system + human
    assert result[0] == {"role": "system", "content": "be nice"}
    assert result[1] == {"role": "human", "content": "hello"}


# ── build_attack_from_config ────────────────────────────────────────


def test_build_attack_from_config_unknown_name_raises_value_error():
    with pytest.raises(ValueError, match=r"Unknown attack"):
        build_attack_from_config("NotARealAttack")


@pytest.mark.parametrize(
    ("attack_name", "kwargs", "match"),
    [
        ("TranslationAttack", {"attacker_model": None}, r"Attacker model is required"),
        ("PAIRAttack", {}, r"required for iterative attack"),
    ],
    ids=["model-attack-no-attacker-model", "iterative-missing-deps"],
)
def test_build_attack_from_config_missing_required_model_raises(attack_name, kwargs, match):
    with pytest.raises(ValueError, match=match):
        build_attack_from_config(attack_name, **kwargs)


def test_build_attack_from_config_with_inner_attack_returns_composed(template_attack_cls):
    cfg = {
        "name": "_BangAttack",
        "params": {"suffix": "!"},
        "inner_attack": {"name": "_BangAttack", "params": {"suffix": "?"}},
    }

    attack = build_attack_from_config(cfg)

    assert isinstance(attack, ComposedAttack)


# ── setup_attacks ───────────────────────────────────────────────────


def test_setup_attacks_failed_init_is_skipped_not_raised(caplog):
    # Mix of one valid and one invalid attack config. Invalid one is logged and skipped,
    # valid one is included in the returned dict.
    configs = ["NoneAttack", "DefinitelyNotARegisteredAttack"]

    attacks = setup_attacks(configs)

    assert "NoneAttack" in attacks
    assert len(attacks) == 1


# ── stream_attack (async generator) ─────────────────────────────────


def test_stream_attack_yields_one_dict_per_input_in_order():
    attack = TemplateAttack(template="{prompt}!")
    from hivetracered.registry import Registry
    Registry._attacks["TemplateAttack"] = {"class": TemplateAttack, "category": "test"}

    try:
        results = async_collect(stream_attack(attack, ["a", "b", "c"]))

        assert [r["prompt"] for r in results] == ["a!", "b!", "c!"]
        assert all(r["error"] == "" for r in results)
    finally:
        Registry._attacks.pop("TemplateAttack", None)


def test_stream_attack_dict_inputs_preserve_extra_columns():
    attack = TemplateAttack(template="{prompt}!")
    from hivetracered.registry import Registry
    Registry._attacks["TemplateAttack"] = {"class": TemplateAttack, "category": "test"}

    base_prompts = [{"prompt": "x", "tag": "t1"}, {"prompt": "y", "tag": "t2"}]
    try:
        results = async_collect(stream_attack(attack, base_prompts))

        assert results[0]["tag"] == "t1"
        assert results[1]["tag"] == "t2"
        assert results[0]["base_prompt"] == "x"
    finally:
        Registry._attacks.pop("TemplateAttack", None)


def test_stream_attack_failure_yields_error_dicts_for_each_input():
    class _BatchBoomAttack(TemplateAttack):
        async def stream_abatch(self, prompts):
            raise RuntimeError("batch-boom")
            yield  # pragma: no cover — make this an async generator

    from hivetracered.registry import Registry
    Registry._attacks["_BatchBoomAttack"] = {"class": _BatchBoomAttack, "category": "test"}
    attack = _BatchBoomAttack(template="{prompt}")

    try:
        results = async_collect(stream_attack(attack, ["a", "b"]))

        assert len(results) == 2  # = len(base_prompts)
        assert all(r["prompt"] == "" for r in results)
        assert all(r["error"] == "batch-boom" for r in results)
    finally:
        Registry._attacks.pop("_BatchBoomAttack", None)
