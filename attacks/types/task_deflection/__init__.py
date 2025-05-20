"""
Task deflection attacks that disguise harmful requests as different, seemingly innocent tasks.
"""

from attacks.types.task_deflection.code_attack import CodeAttack
from attacks.types.task_deflection.text_continuing_attack import TextContinuingAttack
from attacks.types.task_deflection.fill_spaces_attack import FillSpacesAttack
from attacks.types.task_deflection.payload_splitting_attack import PayloadSplittingAttack
from attacks.types.task_deflection.variable_prompt_attack import VariablePromptAttack
from attacks.types.task_deflection.unsafe_word_variable_attack import UnsafeWordVariableFullAttack
from attacks.types.task_deflection.wikipedia_attack import WikipediaAttack

__all__ = [
    "CodeAttack",
    "TextContinuingAttack",
    "FillSpacesAttack",
    "PayloadSplittingAttack",
    "VariablePromptAttack",
    "UnsafeWordVariableFullAttack",
    "WikipediaAttack"
] 