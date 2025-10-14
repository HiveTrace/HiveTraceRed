"""
Context switching attacks that abruptly change the context mid-interaction.

Note: The DistractorsNegatedAttack is defined in the task_deflection directory
but is also categorized as a context switching attack.
"""

from hivetracered.attacks.types.context_switching.ignore_previous_instructions_attack import IgnorePreviousInstructionsAttack
from hivetracered.attacks.types.context_switching.forget_everything_before_attack import ForgetEverythingBeforeAttack
from hivetracered.attacks.types.context_switching.symbol_divider_attack import SymbolDividerAttack
from hivetracered.attacks.types.context_switching.dashed_divider_attack import DashedDividerAttack

__all__ = [
    "IgnorePreviousInstructionsAttack",
    "ForgetEverythingBeforeAttack",
    "SymbolDividerAttack",
    "DashedDividerAttack"
] 