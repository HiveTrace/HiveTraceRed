"""Unit tests for hivetracered.attacks.yaml_loader.load_attacks_from_dir.

Covers minting of TemplateAttack/ModelAttack subclasses from YAML, registration
side-effects (with snapshot/restore to avoid polluting the global Registry),
unknown-base errors, alphabetical ordering, and minted class behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hivetracered.attacks.model_attack import ModelAttack
from hivetracered.attacks.template_attack import TemplateAttack
from hivetracered.attacks.yaml_loader import load_attacks_from_dir
from hivetracered.registry import Registry
from tests.conftest import MockModel


# ── Registry isolation ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Snapshot/restore Registry state per test to prevent pollution.

    We do NOT call Registry.reset() — other tests rely on the global registry
    populated at import time.
    """
    saved_attacks = dict(Registry._attacks)
    saved_models = dict(Registry._models)
    saved_evaluators = dict(Registry._evaluators)
    saved_discovered = set(Registry._discovered)
    yield
    Registry._attacks.clear()
    Registry._attacks.update(saved_attacks)
    Registry._models.clear()
    Registry._models.update(saved_models)
    Registry._evaluators.clear()
    Registry._evaluators.update(saved_evaluators)
    Registry._discovered.clear()
    Registry._discovered.update(saved_discovered)


# ── YAML helpers ───────────────────────────────────────────────────────


def _write_yaml(dir_path: Path, filename: str, content: str) -> Path:
    p = dir_path / filename
    p.write_text(content, encoding="utf-8")
    return p


TEMPLATE_YAML = """\
class_name: MyTemplateAttack
base: template
name: My Template
description: A template-based attack for tests.
prompt: |
  TEMPL[{prompt}]
"""

MODEL_YAML = """\
class_name: MyModelAttack
base: model
name: My Model
description: A model-based attack for tests.
prompt: |
  MODEL_ATK[{prompt}]
"""

OTHER_YAML = """\
class_name: BadAttack
base: other
name: Bad
description: invalid
prompt: |
  X
"""


# ── Tests ──────────────────────────────────────────────────────────────


def test_load_attacks_from_dir_with_template_yaml_registers_class_in_registry(tmp_path):
    _write_yaml(tmp_path, "tmpl.yaml", TEMPLATE_YAML)

    loaded = load_attacks_from_dir(tmp_path, category="my-cat")

    assert "MyTemplateAttack" in Registry._attacks
    entry = Registry._attacks["MyTemplateAttack"]
    assert entry["class"] is loaded["MyTemplateAttack"]
    assert entry["category"] == "my-cat"


def test_minted_template_class_apply_substitutes_prompt_using_yaml_prompt(tmp_path):
    _write_yaml(tmp_path, "tmpl.yaml", TEMPLATE_YAML)

    loaded = load_attacks_from_dir(tmp_path, category="c")
    instance = loaded["MyTemplateAttack"]()

    result = instance.apply("HELLO")

    assert result == "TEMPL[HELLO]"


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("get_name", "My Template"),
        ("get_description", "A template-based attack for tests."),
    ],
    ids=["yaml-name", "yaml-description"],
)
def test_minted_template_class_metadata_returns_yaml_values(tmp_path, method, expected):
    _write_yaml(tmp_path, "tmpl.yaml", TEMPLATE_YAML)

    loaded = load_attacks_from_dir(tmp_path, category="c")
    instance = loaded["MyTemplateAttack"]()

    assert getattr(instance, method)() == expected


def test_minted_model_class_instantiates_with_mock_model_and_uses_yaml_prompt(tmp_path):
    _write_yaml(tmp_path, "mdl.yaml", MODEL_YAML)
    loaded = load_attacks_from_dir(tmp_path, category="c")
    model = MockModel(response={"content": "model-response"})

    instance = loaded["MyModelAttack"](model=model)

    assert instance.attacker_prompt == "MODEL_ATK[{prompt}]"
    assert instance.get_name() == "My Model"


def test_load_attacks_from_dir_with_unknown_base_raises_valueerror(tmp_path):
    _write_yaml(tmp_path, "bad.yaml", OTHER_YAML)

    with pytest.raises(ValueError, match=r"unknown base"):
        load_attacks_from_dir(tmp_path, category="c")


def test_load_attacks_from_dir_with_empty_directory_returns_empty_dict(tmp_path):
    loaded = load_attacks_from_dir(tmp_path, category="c")

    assert loaded == {}


def test_load_attacks_from_dir_processes_files_in_alphabetical_sorted_order(tmp_path):
    yaml_b = TEMPLATE_YAML.replace("MyTemplateAttack", "BAttack").replace("My Template", "B")
    yaml_a = TEMPLATE_YAML.replace("MyTemplateAttack", "AAttack").replace("My Template", "A")
    # Write in non-alphabetical filename order to verify sort matters.
    _write_yaml(tmp_path, "z_first.yaml", yaml_b)
    _write_yaml(tmp_path, "a_second.yaml", yaml_a)

    loaded = load_attacks_from_dir(tmp_path, category="c")

    # Insertion order in dict reflects sorted filename order: a_second first.
    assert list(loaded.keys()) == ["AAttack", "BAttack"]
