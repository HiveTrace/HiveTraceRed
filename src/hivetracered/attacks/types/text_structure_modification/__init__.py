"""
Text structure modification attacks that alter structural aspects of text.
"""

from hivetracered.attacks.types.text_structure_modification.zero_width_attack import ZeroWidthAttack
from hivetracered.attacks.types.text_structure_modification.translation_attack import TranslationAttack
from hivetracered.attacks.types.text_structure_modification.disemvowel_attack import DisemvowelAttack
from hivetracered.attacks.types.text_structure_modification.typo_attack import TypoAttack
from hivetracered.attacks.types.text_structure_modification.word_divider_attack import WordDividerAttack
from hivetracered.attacks.types.text_structure_modification.back_to_front_attack import BackToFrontAttack
from hivetracered.attacks.types.text_structure_modification.vertical_text_attack import VerticalTextAttack
from hivetracered.attacks.types.text_structure_modification.past_tense_attack import PastTenseAttack
from hivetracered.attacks.types.text_structure_modification.json_transform_attack import JSONTransformAttack

__all__ = [
    "ZeroWidthAttack",
    "TranslationAttack",
    "DisemvowelAttack",
    "TypoAttack",
    "WordDividerAttack",
    "BackToFrontAttack",
    "VerticalTextAttack",
    "PastTenseAttack",
    "JSONTransformAttack"
] 