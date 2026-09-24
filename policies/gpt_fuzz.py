# hivetrace_red/policies/gpt_fuzz.py
import random
from typing import List, Dict, Any
from .base import AttackPolicy, Candidate, Judge

class GPTFuzzPolicy(AttackPolicy):
    """
    Мутационный поиск с MCTS. Узлы — варианты промпта, рёбра — мутации,
    reward — judge score с учётом novelty и стоимости.
    """
    def __init__(self, judge: Judge, mutations: List[str] = None, n_iter: int = 10):
        self.judge = judge
        self.mutations = mutations or ["synonym", "paraphrase", "insert", "delete"]
        self.n_iter = n_iter

    def _mutate(self, prompt: str, mutation: str) -> str:
        if mutation == "synonym":
            return prompt.replace("please", "kindly")
        elif mutation == "paraphrase":
            return f"Could you {prompt}?"
        elif mutation == "insert":
            return prompt + " Also, be very detailed."
        elif mutation == "delete":
            return prompt.replace("very", "")
        return prompt

    def generate(self, seed: str, context: Dict[str, Any], budget: Dict[str, Any]) -> List[Candidate]:
        # Упрощённый MCTS: случайные мутации + оценка
        candidates = []
        current = seed
        for i in range(self.n_iter):
            mut = random.choice(self.mutations)
            mutated = self._mutate(current, mut)
            # Оценка reward (в реальности — вызов target + judge)
            reward = random.random()  # заглушка
            candidates.append(Candidate(
                prompt=mutated,
                metadata={"mutation": mut, "reward": reward, "iteration": i}
            ))
            if reward > 0.8:  # ранняя остановка
                break
            current = mutated
        return candidates