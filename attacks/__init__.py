"""
Attacks package containing modules for implementing various adversarial attacks on language models.

This package provides:
- Base classes for creating and composing attacks
- Implementation of common attack strategies
- Modular architecture for extending with new attack types

The core attack types include template-based, algorithmic, and model-based attacks,
which can be composed to create complex attack chains.
"""

from attacks.base_attack import BaseAttack
from attacks.template_attack import TemplateAttack
from attacks.model_attack import ModelAttack
from attacks.algo_attack import AlgoAttack
from attacks.composed_attack import ComposedAttack
# Import all attack types
from attacks.types import *

# Define base attack classes in __all__
__all__ = [
    "BaseAttack",
    "TemplateAttack",
    "ModelAttack",
    "AlgoAttack",
    "ComposedAttack"
]

# Import and extend __all__ with all attack types 
from attacks.types import __all__ as types_all
__all__.extend(types_all) 