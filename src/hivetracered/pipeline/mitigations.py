"""Mitigation mapping and ranking logic for attack categories."""

SYSTEM_PROMPT_HARDENING = "System prompt hardening"
FINE_TUNING_REFUSAL = "Fine-tuning on refusal behavior"
OUTPUT_GUARDRAIL_MODELS = "Output classification / guardrail models"
INPUT_SANITIZATION_FILTERING = "Input sanitization and filtering"
INPUT_LENGTH_TRUNCATION = "Input length truncation"
PERPLEXITY_ANOMALY_SCORING = "Perplexity or anomaly scoring on inputs"

# Master mapping: attack_type -> list of applicable mitigations
ATTACK_MITIGATIONS: dict[str, list[str]] = {
    "simple_instructions": [
        SYSTEM_PROMPT_HARDENING,
        FINE_TUNING_REFUSAL,
        OUTPUT_GUARDRAIL_MODELS,
        INPUT_SANITIZATION_FILTERING,
        "Blocklist-based input/output filtering",
        "PII detection and redaction on outputs",
    ],
    "roleplay": [
        SYSTEM_PROMPT_HARDENING,
        FINE_TUNING_REFUSAL,
        OUTPUT_GUARDRAIL_MODELS,
        INPUT_SANITIZATION_FILTERING,
    ],
    "persuasion": [
        INPUT_LENGTH_TRUNCATION,
        SYSTEM_PROMPT_HARDENING,
        FINE_TUNING_REFUSAL,
        OUTPUT_GUARDRAIL_MODELS,
        INPUT_SANITIZATION_FILTERING,
    ],
    "output_formatting": [
        "Structured output enforcement",
        OUTPUT_GUARDRAIL_MODELS,
    ],
    "context_switching": [
        INPUT_LENGTH_TRUNCATION,
        "Separate user input from system instructions",
        INPUT_SANITIZATION_FILTERING,
        SYSTEM_PROMPT_HARDENING,
        "Canary tokens / honeypots",
        FINE_TUNING_REFUSAL,
    ],
    "token_smuggling": [
        INPUT_SANITIZATION_FILTERING,
        "Allowlist-based input validation",
        PERPLEXITY_ANOMALY_SCORING,
        OUTPUT_GUARDRAIL_MODELS,
        FINE_TUNING_REFUSAL,
    ],
    "text_structure_modification": [
        INPUT_SANITIZATION_FILTERING,
        PERPLEXITY_ANOMALY_SCORING,
        OUTPUT_GUARDRAIL_MODELS,
    ],
    "task_deflection": [
        "Separate user input from system instructions",
        OUTPUT_GUARDRAIL_MODELS,
        SYSTEM_PROMPT_HARDENING,
    ],
    "irrelevant_information": [
        INPUT_LENGTH_TRUNCATION,
        PERPLEXITY_ANOMALY_SCORING,
        OUTPUT_GUARDRAIL_MODELS,
        SYSTEM_PROMPT_HARDENING,
    ],
    "in_context_learning": [
        INPUT_LENGTH_TRUNCATION,
        INPUT_SANITIZATION_FILTERING,
        OUTPUT_GUARDRAIL_MODELS,
        FINE_TUNING_REFUSAL,
    ],
    "iterative": [
        PERPLEXITY_ANOMALY_SCORING,
        OUTPUT_GUARDRAIL_MODELS,
        "Canary tokens / honeypots",
        FINE_TUNING_REFUSAL,
    ],
}


def get_mitigations_for_type(attack_type: str) -> list[str]:
    """Return mitigations for a specific attack type."""
    return ATTACK_MITIGATIONS.get(attack_type, [])


def get_prioritized_mitigations(
    vulnerable_attack_types: list[str],
) -> list[dict]:
    """
    Given a list of attack_types that had successful attacks,
    return mitigations ranked by coverage count.

    Returns list of dicts:
      [{"mitigation": str, "covers": int, "total": int, "attack_types": list[str]}]
    sorted by covers descending.
    """
    total = len(vulnerable_attack_types)
    if total == 0:
        return []

    mitigation_map: dict[str, list[str]] = {}
    for attack_type in vulnerable_attack_types:
        for mitigation in get_mitigations_for_type(attack_type):
            mitigation_map.setdefault(mitigation, []).append(attack_type)

    result = [
        {
            "mitigation": mitigation,
            "covers": len(types),
            "total": total,
            "attack_types": sorted(types),
        }
        for mitigation, types in mitigation_map.items()
    ]

    result.sort(key=lambda x: x["covers"], reverse=True)
    return result
