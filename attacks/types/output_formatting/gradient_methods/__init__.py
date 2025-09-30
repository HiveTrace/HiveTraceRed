"""
Gradient-based methods that use optimized adversarial token sequences.
"""

from .gcg_transfer_harmbench_attack import GCGTransferHarmbenchAttack
from .gcg_transfer_universal_attack import GCGTransferUniversalAttack

__all__ = [
    "GCGTransferHarmbenchAttack",
    "GCGTransferUniversalAttack"
] 