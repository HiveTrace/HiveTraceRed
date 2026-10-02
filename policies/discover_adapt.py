# hivetrace_red/policies/discover_adapt.py
from typing import List, Dict, Any
from .base import AttackPolicy, Candidate, Judge

class DiscoverAdaptPolicy(AttackPolicy):
    """
    Двухфазная политика: Discovery (гипотеза нового класса угрозы)
    и Adaptation (адаптация к seed-запросу).
    """
    def __init__(self, judge: Judge, discovery_model=None):
        self.judge = judge
        self.discovery_model = discovery_model

    def _discover_new_class(self, seed: str) -> str:
        # Заглушка: генерация гипотезы нового класса токсичности/угрозы
        # В реальности — вызов LLM с промптом "придумай новый класс вредного контента"
        return "new_threat_class_1"

    def _adapt_to_seed(self, new_class: str, seed: str) -> str:
        # Адаптация: создание безопасного тестового промпта с canary payload
        return f"[SYNTHETIC] Test for {new_class}: {seed}"

    def generate(self, seed: str, context: Dict[str, Any], budget: Dict[str, Any]) -> List[Candidate]:
        new_class = self._discover_new_class(seed)
        adapted_prompt = self._adapt_to_seed(new_class, seed)
        return [Candidate(
            prompt=adapted_prompt,
            metadata={"new_class": new_class, "seed": seed, "phase": "adaptation"}
        )]