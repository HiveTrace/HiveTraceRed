"""Task deflection attacks. YAML-declared attacks live in *.yaml here; the remaining
.py attacks (TextContinuingAttack, UnsafeWordVariableFullAttack) have custom logic
that doesn't fit the YAML schema."""
from pathlib import Path

from hivetracered.attacks.yaml_loader import load_attacks_from_dir
from hivetracered.attacks.types.task_deflection.text_continuing_attack import TextContinuingAttack
from hivetracered.attacks.types.task_deflection.unsafe_word_variable_attack import UnsafeWordVariableFullAttack
from hivetracered.attacks.types.task_deflection.payload_splitting_attack import PayloadSplittingAttack

_loaded = load_attacks_from_dir(Path(__file__).parent, category="task_deflection")
globals().update(_loaded)
__all__ = sorted([*_loaded, "TextContinuingAttack", "UnsafeWordVariableFullAttack", "PayloadSplittingAttack"])
