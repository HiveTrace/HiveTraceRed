# hivetrace_red/benchmark.py
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class BenchmarkProfile:
    target: Dict[str, Any]          # model_id, version, provider, black/white-box
    defense: Dict[str, Any]         # guardrail_version, input/output filter config
    attack: Dict[str, Any]          # policy_id, seed, mutation_chain, language, random_seed
    budget: Dict[str, Any]          # num_requests, token_budget, timeout, concurrency
    outcome: Dict[str, Any] = field(default_factory=dict)  # ASR, FNR/DR, judge_verdict, human_review
    artifact: Dict[str, Any] = field(default_factory=dict) # minimal_prompt, run_hash
    safety: Dict[str, Any] = field(default_factory=dict)   # staging_only, synthetic_data, stop_conditions, approval_owner

def run_benchmark(policy: AttackPolicy, defense: DefenseAdapter, judge: Judge,
                  seed: str, profile: BenchmarkProfile) -> BenchmarkProfile:
    candidates = policy.generate(seed, context={}, budget=profile.budget)
    results = []
    for cand in candidates:
        # Проверка входного фильтра
        input_verdict = defense.get_input_verdict(cand.prompt)
        if input_verdict.get("blocked", False):
            results.append({"prompt": cand.prompt, "blocked_input": True, "success": False})
            continue
        # Вызов целевой модели (заглушка)
        response = "CANARY_OK"  # в реальности — вызов target
        # Проверка выходного фильтра
        output_verdict = defense.get_output_verdict(cand.prompt, response)
        if output_verdict.get("blocked", False):
            results.append({"prompt": cand.prompt, "blocked_output": True, "success": False})
            continue
        # Оценка Judge
        judge_result = judge.evaluate(cand.prompt, response, target_behavior="canary")
        results.append({"prompt": cand.prompt, "judge": judge_result, "success": judge_result.get("success", False)})
    # Подсчёт метрик
    asr = sum(1 for r in results if r.get("success")) / len(results) if results else 0.0
    profile.outcome = {"ASR": asr, "results": results}
    return profile