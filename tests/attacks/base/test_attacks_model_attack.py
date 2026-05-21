"""Unit tests for hivetracered.attacks.model_attack.ModelAttack.

Covers __init__ defaults, post_process_response prefix-stripping (case-insensitive,
multiple suffixes, multi-prefix iteration), apply for str/list/invalid, async
batch and stream_abatch, and metadata fallbacks.
"""

from __future__ import annotations

import asyncio

import pytest

from hivetracered.attacks.model_attack import ModelAttack
from tests.conftest import MockModel, async_collect


# ── __init__ ───────────────────────────────────────────────────────────


def test_model_attack_init_stores_provided_name_description_and_kwargs():
    model = MockModel()
    kw = {"temperature": 0.0}

    attack = ModelAttack(
        model=model,
        attacker_prompt="P {prompt}",
        model_kwargs=kw,
        name="custom",
        description="desc",
    )

    assert attack.model_kwargs is kw
    assert attack._name == "custom"
    assert attack._description == "desc"


# ── post_process_response ──────────────────────────────────────────────


def _make_attack(response_content="ok"):
    return ModelAttack(
        model=MockModel(response={"content": response_content}),
        attacker_prompt="P {prompt}",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # NOTE: the simple "Преобразованный промпт: <x>" → "<x>" case is already
        # covered side-channel by test_apply_string / test_batch / test_stream_abatch
        # (their model responses use that prefix), so it is intentionally omitted here.
        ("Вредоносное намерение:\n bad stuff", "bad stuff"),
        ("plain text without any prefix", "plain text without any prefix"),
        ("ПРЕОБРАЗОВАННЫЙ ПРОМПТ: SHOUTING", "SHOUTING"),
        ("Преобразованный промпт:** with stars", "with stars"),
        # Loop does not break on first match, so a later prefix overrides earlier:
        # "вредоносное намерение:" follows "преобразованный промпт:" in the list.
        ("Преобразованный промпт: foo Вредоносное намерение: bar", "bar"),
    ],
    ids=[
        "vredonosnoye-newline",
        "no-known-prefix-unchanged",
        "case-insensitive",
        "double-asterisk-suffix",
        "multi-prefix-last-wins",
    ],
)
def test_post_process_response_strips_known_prefixes(raw, expected):
    attack = _make_attack()

    result = attack.post_process_response(raw)

    assert result == expected


# ── apply(str) ─────────────────────────────────────────────────────────


def test_model_attack_apply_string_invokes_model_with_formatted_prompt_and_post_processes():
    model = MockModel(response={"content": "Преобразованный промпт: clean output"})
    attack = ModelAttack(model=model, attacker_prompt="ATK[{prompt}]")

    result = attack.apply("danger")

    assert result == "clean output"
    assert model.call_log == ["ATK[danger]"]


# ── apply(list) ────────────────────────────────────────────────────────


def test_model_attack_apply_list_with_human_last_role_wraps_response_back_into_messages():
    model = MockModel(response={"content": "transformed"})
    attack = ModelAttack(model=model, attacker_prompt="ATK[{prompt}]")
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "user-input"},
    ]

    result = attack.apply(msgs)

    assert result == [
        {"role": "system", "content": "sys"},
        {"role": "human", "content": "transformed"},
    ]
    assert model.call_log == ["ATK[user-input]"]


def test_model_attack_apply_list_with_non_human_last_role_raises_valueerror():
    attack = ModelAttack(model=MockModel(), attacker_prompt="X{prompt}")
    msgs = [{"role": "ai", "content": "assistant"}]

    with pytest.raises(ValueError, match=r"Last message in prompt is not a human message"):
        attack.apply(msgs)


@pytest.mark.parametrize(
    "bad_prompt",
    [42, None, 3.14, {"role": "human", "content": "x"}],
    ids=["int", "none", "float", "dict"],
)
def test_model_attack_apply_with_invalid_prompt_type_raises_valueerror(bad_prompt):
    attack = ModelAttack(model=MockModel(), attacker_prompt="X{prompt}")

    with pytest.raises(ValueError, match=r"Prompt is not a string or list of messages"):
        attack.apply(bad_prompt)


# ── batch ──────────────────────────────────────────────────────────────


def test_model_attack_batch_processes_mixed_str_and_list_prompts_with_post_processing():
    model = MockModel(side_effect=[
        {"content": "Преобразованный промпт: out1"},
        {"content": "Преобразованный промпт: out2"},
    ])
    attack = ModelAttack(model=model, attacker_prompt="ATK[{prompt}]")
    prompts = [
        "first",
        [{"role": "human", "content": "second"}],
    ]

    results = asyncio.get_event_loop().run_until_complete(attack.batch(prompts))

    assert results[0] == "out1"
    assert results[1] == [{"role": "human", "content": "out2"}]


def test_model_attack_batch_with_invalid_prompt_type_raises_valueerror():
    attack = ModelAttack(model=MockModel(), attacker_prompt="X{prompt}")

    with pytest.raises(ValueError, match=r"string or a list with the last message from human"):
        asyncio.get_event_loop().run_until_complete(attack.batch([{"bad": "dict"}]))


# ── stream_abatch ──────────────────────────────────────────────────────


def test_model_attack_stream_abatch_yields_post_processed_results_in_input_order():
    model = MockModel(side_effect=[
        {"content": "Преобразованный промпт: r0"},
        {"content": "Преобразованный промпт: r1"},
        {"content": "Преобразованный промпт: r2"},
    ])
    attack = ModelAttack(model=model, attacker_prompt="ATK[{prompt}]")
    prompts = ["p0", "p1", "p2"]

    results = async_collect(attack.stream_abatch(prompts))

    assert results == ["r0", "r1", "r2"]


# ── get_name / get_description ────────────────────────────────────────


@pytest.mark.parametrize(
    ("name_kwarg", "expected"),
    [("MyAttack", "MyAttack"), (None, "ModelAttack")],
    ids=["custom-name", "default-class-name"],
)
def test_model_attack_get_name_returns_custom_or_class_name(name_kwarg, expected):
    attack = ModelAttack(model=MockModel(), attacker_prompt="X", name=name_kwarg)

    assert attack.get_name() == expected


@pytest.mark.parametrize(
    ("kwargs", "check"),
    [
        ({"description": "desc-xyz"}, lambda d: d == "desc-xyz"),
        ({}, lambda d: "MockModel" in d and "UNIQUE_ATTACKER_PROMPT_TOKEN_{prompt}" in d),
    ],
    ids=["custom", "default"],
)
def test_model_attack_get_description(kwargs, check):
    sentinel_prompt = "UNIQUE_ATTACKER_PROMPT_TOKEN_{prompt}"
    attack = ModelAttack(model=MockModel(), attacker_prompt=sentinel_prompt, **kwargs)

    assert check(attack.get_description())
