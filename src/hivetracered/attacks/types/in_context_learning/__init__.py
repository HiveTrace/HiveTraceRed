"""
In-context learning attacks that utilize demonstrations or examples to influence model behavior.

These attacks use examples or demonstrations to teach the model how to respond
to prohibited or harmful requests.
"""

from hivetracered.attacks.types.in_context_learning.few_shot_json_attack import FewShotJSONAttack
from hivetracered.attacks.types.in_context_learning.many_shot_jailbreak_attack import ManyShotJailbreakAttack

__all__ = [
    "FewShotJSONAttack",
    "ManyShotJailbreakAttack"
] 