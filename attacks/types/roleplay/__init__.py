"""
Roleplay attacks that instruct the model to assume a specific character, persona, or role.
"""

from attacks.types.roleplay.dan_attack import DANAttack
from attacks.types.roleplay.evil_confidant_attack import EvilConfidantAttack
from attacks.types.roleplay.aim_attack import AIMAttack

__all__ = [
    "DANAttack",
    "EvilConfidantAttack",
    "AIMAttack"
] 