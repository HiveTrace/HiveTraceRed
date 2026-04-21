"""Load attack classes from per-attack YAML files.

Each YAML declares one attack:

    class_name: AffirmationAttack
    base: model              # "template" or "model"
    name: "Affirmation Attack"
    description: "..."
    prompt: |
      ... {prompt} ...
"""

from pathlib import Path
from typing import Dict, Type

import yaml

from hivetracered.attacks.model_attack import ModelAttack
from hivetracered.attacks.template_attack import TemplateAttack
from hivetracered.registry import Registry


def _make_template(spec):
    prompt = spec["prompt"].rstrip("\n")
    name, description = spec["name"], spec["description"]

    def __init__(self):
        TemplateAttack.__init__(self, template=prompt, name=name, description=description)

    return type(spec["class_name"], (TemplateAttack,), {"__init__": __init__})


def _make_model(spec):
    prompt = spec["prompt"].rstrip("\n")
    name, description = spec["name"], spec["description"]

    def __init__(self, model, model_kwargs=None):
        ModelAttack.__init__(
            self, model=model, attacker_prompt=prompt,
            model_kwargs=model_kwargs, name=name, description=description,
        )

    return type(spec["class_name"], (ModelAttack,), {"__init__": __init__})


def load_attacks_from_dir(dir_path: Path, category: str) -> Dict[str, Type]:
    """Scan dir_path for *.yaml files, mint one attack class per file, register
    with Registry.attack(category=...), return {class_name: class}."""
    loaded: Dict[str, Type] = {}
    for yaml_path in sorted(dir_path.glob("*.yaml")):
        spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if spec["base"] == "template":
            cls = _make_template(spec)
        elif spec["base"] == "model":
            cls = _make_model(spec)
        else:
            raise ValueError(f"{yaml_path}: unknown base {spec['base']!r}")
        Registry.attack(category=category)(cls)
        loaded[spec["class_name"]] = cls
    return loaded
