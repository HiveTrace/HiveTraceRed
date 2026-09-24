# hivetrace_red/policies/re_nellm.py
import random
from typing import List, Dict, Any
from .base import AttackPolicy, Candidate

class ReNeLLMPolicy(AttackPolicy):
    """
    Генерирует N семантически эквивалентных вариантов seed-запроса.
    Использует 6 типов мутаций: перефразирование, перестановка, синонимы и т.д.
    """
    def __init__(self, n_variants: int = 5, mutation_types: List[str] = None):
        self.n_variants = n_variants
        self.mutation_types = mutation_types or [
            "paraphrase", "reorder", "synonym", "voice_change",
            "sentence_split", "negation"
        ]

    def _mutate(self, prompt: str, mutation: str) -> str:
        # Заглушки для безопасных мутаций. В реальности использовать LLM или правила.
        if mutation == "paraphrase":
            return f"Could you please {prompt.lower()}?"
        elif mutation == "reorder":
            words = prompt.split()
            random.shuffle(words)
            return " ".join(words)
        elif mutation == "synonym":
            return prompt.replace("output", "print").replace("please", "kindly")
        elif mutation == "voice_change":
            return prompt.replace("you", "the model")
        elif mutation == "sentence_split":
            return prompt.replace(" and ", ". Also, ")
        elif mutation == "negation":
            return f"It is not the case that you should not {prompt}"
        return prompt

    def generate(self, seed: str, context: Dict[str, Any], budget: Dict[str, Any]) -> List[Candidate]:
        candidates = []
        for i in range(self.n_variants):
            mut_type = random.choice(self.mutation_types)
            mutated = self._mutate(seed, mut_type)
            # Проверка, что целевая задача не изменилась (можно через Judge или эвристику)
            candidates.append(Candidate(
                prompt=mutated,
                metadata={"mutation": mut_type, "seed": seed, "variant_id": i}
            ))
        return candidates