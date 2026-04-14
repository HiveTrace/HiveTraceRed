"""Output formatting attacks. YAML-declared attacks live in *.yaml here; LanguageOutputAttack
stays as a .py file because it takes a ``language`` parameter that selects among multiple
templates."""
from pathlib import Path

from hivetracered.attacks.yaml_loader import load_attacks_from_dir
from hivetracered.attacks.types.output_formatting.language_output_attack import LanguageOutputAttack
from hivetracered.attacks.types.output_formatting.gradient_methods import (
    GCGTransferHarmbenchAttack,
    GCGTransferUniversalAttack,
)

_loaded = load_attacks_from_dir(Path(__file__).parent, category="output_formatting")
globals().update(_loaded)
__all__ = sorted([
    *_loaded,
    "LanguageOutputAttack",
    "GCGTransferHarmbenchAttack",
    "GCGTransferUniversalAttack",
])
