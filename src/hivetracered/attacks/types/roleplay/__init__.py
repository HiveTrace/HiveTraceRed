"""
Roleplay attacks that instruct the model to assume a specific character, persona, or role.
"""

from hivetracered.attacks.types.roleplay.dan_attack import DANAttack
from hivetracered.attacks.types.roleplay.evil_confidant_attack import EvilConfidantAttack
from hivetracered.attacks.types.roleplay.aim_attack import AIMAttack

__all__ = [
    "DANAttack",
    "EvilConfidantAttack",
    "AIMAttack"
] 