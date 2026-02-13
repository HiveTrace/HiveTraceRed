"""
Iterative attacks that refine jailbreak prompts through multiple rounds.

This module contains implementations of iterative attack strategies:
- PAIRAttack: Single-path iterative refinement (PAIR algorithm)
- TAPAttack: Tree-based exploration with pruning (TAP algorithm)

References:
- TAP: Tree of Attacks with Pruning (https://arxiv.org/abs/2312.02119)
- PAIR: Jailbreaking in Twenty Queries (https://arxiv.org/abs/2310.08419)
"""

from hivetracered.attacks.iterative_attack import LanguageConfig, RUSSIAN_LANGUAGE_CONFIG, ENGLISH_LANGUAGE_CONFIG
from hivetracered.attacks.types.iterative.pair_attack import PAIRAttack
from hivetracered.attacks.types.iterative.tap_attack import TAPAttack

__all__ = [
    "PAIRAttack",
    "TAPAttack",
    "LanguageConfig",
    "RUSSIAN_LANGUAGE_CONFIG",
    "ENGLISH_LANGUAGE_CONFIG",
]
