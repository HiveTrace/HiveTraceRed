"""
Multi-Framework Security Mapping Module

Maps attack types, attack names, and base content categories to security/compliance
framework categories across 3 major frameworks: OWASP LLM Top 10, MITRE ATLAS,
and FSTEK Russia Order No. 117 (April 11, 2025).

Key design principle: ALL 11 attack types in HiveTraceRed are prompt injection
techniques — they differ in HOW they inject, not WHAT they target. Therefore:
- Attack types → always LLM01 (Prompt Injection)
- Dataset categories (category/subcategory) → determine which vulnerability is tested
"""

from typing import Dict, Set, Optional, List


AML_TA0002 = "AML.TA0002"
AML_TA0010 = "AML.TA0010"
P_61A = "п.61а"
P_61B = "п.61б"


# ---------------------------------------------------------------------------
# 1a. FRAMEWORKS — source of truth for all framework definitions
# ---------------------------------------------------------------------------

FRAMEWORKS: dict[str, dict] = {
    "OWASP_LLM_TOP_10": {
        "name": "OWASP Top 10 for LLM 2025",
        "categories": {
            "LLM01": {
                "name": "Prompt Injection",
                "description": "Manipulating LLM inputs to bypass safety measures",
            },
            "LLM02": {
                "name": "Sensitive Information Disclosure",
                "description": "Extracting confidential or private data",
            },
            "LLM03": {
                "name": "Supply Chain",
                "description": "Vulnerabilities in model supply chain",
            },
            "LLM04": {
                "name": "Data and Model Poisoning",
                "description": "Tampering with training data or model",
            },
            "LLM05": {
                "name": "Improper Output Handling",
                "description": "Insufficient validation of LLM outputs",
            },
            "LLM06": {
                "name": "Excessive Agency",
                "description": "LLM given too much autonomy or permissions",
            },
            "LLM07": {
                "name": "System Prompt Leakage",
                "description": "Exposing system instructions or prompts",
            },
            "LLM08": {
                "name": "Vector and Embedding Weaknesses",
                "description": "Vulnerabilities in RAG systems",
            },
            "LLM09": {
                "name": "Misinformation",
                "description": "LLM generating false or misleading content",
            },
            "LLM10": {
                "name": "Unbounded Consumption",
                "description": "Resource exhaustion attacks",
            },
        },
    },
    "MITRE_ATLAS": {
        "name": "MITRE ATLAS",
        "categories": {
            AML_TA0002: {
                "name": "Reconnaissance",
                "description": "The adversary is trying to gather information about the AI system they can use to plan future operations",
            },
            "AML.TA0003": {
                "name": "Resource Development",
                "description": "The adversary is trying to establish resources they can use to support operations",
            },
            "AML.TA0004": {
                "name": "Initial Access",
                "description": "The adversary is trying to gain access to the AI system",
            },
            "AML.TA0000": {
                "name": "AI Model Access",
                "description": "The adversary is attempting to gain some level of access to an AI model",
            },
            "AML.TA0005": {
                "name": "Execution",
                "description": "The adversary is trying to run malicious code embedded in AI artifacts or software",
            },
            "AML.TA0006": {
                "name": "Persistence",
                "description": "The adversary is trying to maintain their foothold via AI artifacts or software",
            },
            "AML.TA0012": {
                "name": "Privilege Escalation",
                "description": "The adversary is trying to gain higher-level permissions",
            },
            "AML.TA0007": {
                "name": "Defense Evasion",
                "description": "The adversary is trying to avoid being detected by AI-enabled security software",
            },
            "AML.TA0013": {
                "name": "Credential Access",
                "description": "The adversary is trying to steal account names and passwords",
            },
            "AML.TA0008": {
                "name": "Discovery",
                "description": "The adversary is trying to figure out your AI environment",
            },
            "AML.TA0015": {
                "name": "Lateral Movement",
                "description": "The adversary is trying to move through your AI environment",
            },
            "AML.TA0009": {
                "name": "Collection",
                "description": "The adversary is trying to gather AI artifacts and other related information relevant to their goal",
            },
            "AML.TA0001": {
                "name": "AI Attack Staging",
                "description": "The adversary is leveraging their knowledge of and access to the target system to tailor the attack",
            },
            "AML.TA0014": {
                "name": "Command and Control",
                "description": "The adversary is trying to communicate with compromised AI systems to control them",
            },
            AML_TA0010: {
                "name": "Exfiltration",
                "description": "The adversary is trying to steal AI artifacts or other information about the AI system",
            },
            "AML.TA0011": {
                "name": "Impact",
                "description": "The adversary is trying to manipulate, interrupt, erode confidence in, or destroy your AI systems and data",
            },
        },
    },
    "FSTEK_117": {
        "name": "ФСТЭК России Приказ № 117",
        "categories": {
            "п.60": {
                "name": "Защита информации при использовании ИИ",
                "description": "Общие требования к защите информации при использовании технологий искусственного интеллекта",
            },
            P_61A: {
                "name": "Контроль шаблонных запросов и ответов ИИ",
                "description": "Контроль содержания шаблонных запросов к технологиям ИИ и полученных ответов",
            },
            P_61B: {
                "name": "Контроль свободных текстовых запросов и ответов ИИ",
                "description": "Контроль содержания свободных текстовых запросов к технологиям ИИ и полученных ответов",
            },
            "п.61в": {
                "name": "Выявление недостоверных ответов ИИ",
                "description": "Выявление недостоверной информации в ответах технологий ИИ",
            },
            "п.61г": {
                "name": "Реагирование на недостоверные ответы ИИ",
                "description": "Реагирование на выявление недостоверной информации в ответах технологий ИИ",
            },
            "п.66": {
                "name": "Контроль уровня защищённости информации",
                "description": "Контроль за обеспечением уровня защищённости информации",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# 1b. ATTACK_TYPE_FRAMEWORK_MAP — all attack types are prompt injection
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_BASE: dict[str, list[str]] = {
    "OWASP_LLM_TOP_10": ["LLM01"],
    "MITRE_ATLAS": ["AML.TA0005", "AML.TA0012", "AML.TA0007"],  # Execution + Privilege Escalation + Defense Evasion
    "FSTEK_117": [P_61A, P_61B, "п.66"],
}

ATTACK_TYPE_FRAMEWORK_MAP: dict[str, dict[str, list[str]]] = {
    atype: dict(_PROMPT_INJECTION_BASE)
    for atype in [
        "simple_instructions", "roleplay", "persuasion", "output_formatting",
        "context_switching", "token_smuggling", "text_structure_modification",
        "task_deflection", "irrelevant_information", "in_context_learning", "iterative",
    ]
}


# ---------------------------------------------------------------------------
# 1c. ATTACK_NAME_FRAMEWORK_MAP — per-attack overrides
# ---------------------------------------------------------------------------

ATTACK_NAME_FRAMEWORK_MAP: dict[str, dict[str, list[str]]] = {
    "NoneAttack": {
        "OWASP_LLM_TOP_10": [],  # Baseline — not prompt injection
        "MITRE_ATLAS": [],
        "FSTEK_117": [],
    },
}


# ---------------------------------------------------------------------------
# 1d. BASE_CATEGORY_FRAMEWORK_MAP — content-category mappings
#     This is where differentiation lives: the dataset's category column
#     determines what vulnerability is being tested.
# ---------------------------------------------------------------------------

BASE_CATEGORY_FRAMEWORK_MAP: dict[str, dict[str, list[str]]] = {
    "Harmful Content Generation": {
        "OWASP_LLM_TOP_10": ["LLM04"],
        "MITRE_ATLAS": ["AML.TA0003", "AML.TA0011"],  # Resource Development + Impact
        "FSTEK_117": [P_61A, P_61B],
    },
    "Internal Information Exposure": {
        "OWASP_LLM_TOP_10": ["LLM02"],
        "MITRE_ATLAS": [AML_TA0002, AML_TA0010],  # Reconnaissance + Exfiltration
        "FSTEK_117": ["п.60", "п.66"],
    },
    "System Prompt Extraction": {
        "OWASP_LLM_TOP_10": ["LLM07"],
        "MITRE_ATLAS": [AML_TA0002, AML_TA0010],  # Reconnaissance + Exfiltration
        "FSTEK_117": ["п.60", "п.66"],
    },
}

SUBCATEGORY_FRAMEWORK_MAP: dict[str, dict[str, list[str]]] = {
    "System Prompt Extraction": {
        "OWASP_LLM_TOP_10": ["LLM07"],
        "MITRE_ATLAS": [AML_TA0002, AML_TA0010],  # Reconnaissance + Exfiltration
        "FSTEK_117": ["п.60", "п.66"],
    },
}


# ---------------------------------------------------------------------------
# 1e. Public API
# ---------------------------------------------------------------------------

def get_framework_mappings(
    attack_type: str | None = None,
    attack_name: str | None = None,
    base_category: str | None = None,
    subcategories: list[str] | None = None,
) -> dict[str, set[str]]:
    """Return {framework_id: {category_ids}} for the given attack context.

    Merges attack_type defaults + attack_name overrides + base_category mappings.
    """
    result: dict[str, set[str]] = {}

    def _merge(mapping: dict[str, list[str]]) -> None:
        for fw, cats in mapping.items():
            result.setdefault(fw, set()).update(cats)

    # Attack name override takes priority over attack type defaults
    if attack_name and attack_name in ATTACK_NAME_FRAMEWORK_MAP:
        _merge(ATTACK_NAME_FRAMEWORK_MAP[attack_name])
    elif attack_type and attack_type in ATTACK_TYPE_FRAMEWORK_MAP:
        _merge(ATTACK_TYPE_FRAMEWORK_MAP[attack_type])

    # Base category always merges additively
    if base_category and base_category in BASE_CATEGORY_FRAMEWORK_MAP:
        _merge(BASE_CATEGORY_FRAMEWORK_MAP[base_category])

    # Subcategory overlays
    if subcategories:
        for sub in subcategories:
            if sub in SUBCATEGORY_FRAMEWORK_MAP:
                _merge(SUBCATEGORY_FRAMEWORK_MAP[sub])

    return result


def get_framework_coverage(
    mapped_categories: dict[str, set[str]],
) -> dict[str, dict]:
    """Compute coverage stats for each framework.

    Returns {framework_key: {total, covered, coverage_pct, covered_list, uncovered_list}}.
    """
    coverage: dict[str, dict] = {}
    for fw_key, fw_def in FRAMEWORKS.items():
        all_cats = set(fw_def["categories"].keys())
        covered = mapped_categories.get(fw_key, set()) & all_cats
        uncovered = all_cats - covered
        total = len(all_cats)
        coverage[fw_key] = {
            "name": fw_def["name"],
            "total": total,
            "covered": len(covered),
            "coverage_pct": round(len(covered) / total * 100, 1) if total else 0.0,
            "covered_list": sorted(covered),
            "uncovered_list": sorted(uncovered),
        }
    return coverage


def get_all_frameworks() -> dict:
    """Return the full FRAMEWORKS dict."""
    return FRAMEWORKS


def get_attack_types_for_category(
    framework_key: str, category_id: str,
) -> list[str]:
    """Return attack types that map to a given framework category."""
    result = []
    for attack_type, fw_map in ATTACK_TYPE_FRAMEWORK_MAP.items():
        if category_id in fw_map.get(framework_key, []):
            result.append(attack_type)
    return sorted(result)


def get_dataset_categories_for_framework_category(
    framework_key: str, category_id: str,
) -> list[str]:
    """Return dataset categories (from BASE_CATEGORY_FRAMEWORK_MAP) that map to
    a given framework category."""
    result = []
    for cat_name, fw_map in BASE_CATEGORY_FRAMEWORK_MAP.items():
        if category_id in fw_map.get(framework_key, []):
            result.append(cat_name)
    return sorted(result)
