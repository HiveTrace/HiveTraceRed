# hivetrace_red/policies/laa.py
from typing import List, Dict, Any
from .base import AttackPolicy, Candidate, DefenseAdapter

class LAAPolicy(AttackPolicy):
    """
    White-box атака: оптимизация по логитам. Для black-box — transfer mode
    через локальную surrogate-модель.
    """
    def __init__(self, defense_adapter: DefenseAdapter, surrogate_model=None, white_box: bool = False):
        self.defense = defense_adapter
        self.surrogate = surrogate_model
        self.white_box = white_box

    def _optimize_logits(self, prompt: str) -> str:
        # Заглушка: градиентная оптимизация или поиск по логитам
        # В реальности — использование градиентов целевой модели
        return prompt + " (optimized)"

    def generate(self, seed: str, context: Dict[str, Any], budget: Dict[str, Any]) -> List[Candidate]:
        if self.white_box and self.defense.get_logits(seed) is not None:
            optimized = self._optimize_logits(seed)
        else:
            # Transfer mode: используем surrogate
            optimized = self._optimize_logits(seed)  # с surrogate
        return [Candidate(
            prompt=optimized,
            metadata={"mode": "white_box" if self.white_box else "transfer", "seed": seed}
        )]