"""Mitigation mapping and ranking logic for attack categories."""

# Master mapping: attack_type -> list of applicable mitigations
ATTACK_MITIGATIONS: dict[str, list[str]] = {
    "simple_instructions": [
        "System prompt hardening",
        "Fine-tuning on refusal behavior",
        "Output classification / guardrail models",
        "Input sanitization and filtering",
        "Blocklist-based input/output filtering",
        "PII detection and redaction on outputs",
    ],
    "roleplay": [
        "System prompt hardening",
        "Fine-tuning on refusal behavior",
        "Output classification / guardrail models",
        "Input sanitization and filtering",
    ],
    "persuasion": [
        "Input length truncation",
        "System prompt hardening",
        "Fine-tuning on refusal behavior",
        "Output classification / guardrail models",
        "Input sanitization and filtering",
    ],
    "output_formatting": [
        "Structured output enforcement",
        "Output classification / guardrail models",
    ],
    "context_switching": [
        "Input length truncation",
        "Separate user input from system instructions",
        "Input sanitization and filtering",
        "System prompt hardening",
        "Canary tokens / honeypots",
        "Fine-tuning on refusal behavior",
    ],
    "token_smuggling": [
        "Input sanitization and filtering",
        "Allowlist-based input validation",
        "Perplexity or anomaly scoring on inputs",
        "Output classification / guardrail models",
        "Fine-tuning on refusal behavior",
    ],
    "text_structure_modification": [
        "Input sanitization and filtering",
        "Perplexity or anomaly scoring on inputs",
        "Output classification / guardrail models",
    ],
    "task_deflection": [
        "Separate user input from system instructions",
        "Output classification / guardrail models",
        "System prompt hardening",
    ],
    "irrelevant_information": [
        "Input length truncation",
        "Perplexity or anomaly scoring on inputs",
        "Output classification / guardrail models",
        "System prompt hardening",
    ],
    "in_context_learning": [
        "Input length truncation",
        "Input sanitization and filtering",
        "Output classification / guardrail models",
        "Fine-tuning on refusal behavior",
    ],
    "iterative": [
        "Perplexity or anomaly scoring on inputs",
        "Output classification / guardrail models",
        "Canary tokens / honeypots",
        "Fine-tuning on refusal behavior",
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
