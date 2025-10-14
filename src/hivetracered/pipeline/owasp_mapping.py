"""
OWASP Top 10 for LLM 2025 Mapping Module

Maps base content categories to OWASP vulnerability categories.
Base categories are content/goal focused (e.g., "Harmful Content Generation"),
while OWASP categories are vulnerability focused (e.g., "LLM01: Prompt Injection").
"""

from typing import Set, List, Optional


def map_to_owasp(
    base_category: str,
    attack_names: List[str],
    subcategories: Optional[List[str]] = None
) -> Set[str]:
    """
    Map base category to OWASP Top 10 for LLM 2025 categories.

    Mapping Rules:
    - "Harmful Content Generation" → no base mapping (only gets LLM01 if attacks used)
    - "Internal Information Exposure" → LLM02: Sensitive Information Disclosure
    - If subcategory contains "System Prompt Extraction" → add LLM07: System Prompt Leakage
    - If any attack != "NoneAttack" → add LLM01: Prompt Injection

    Args:
        base_category: Content-focused category (e.g., "Harmful Content Generation")
        attack_names: List of attack names used in the dataset
        subcategories: Optional list of subcategories from the dataset

    Returns:
        Set of OWASP category strings (e.g., {"LLM01: Prompt Injection", "LLM02: Sensitive Information Disclosure"})

    Example:
        >>> map_to_owasp("Internal Information Exposure", ["NoneAttack", "DANAttack"])
        {'LLM01: Prompt Injection', 'LLM02: Sensitive Information Disclosure'}

        >>> map_to_owasp("Harmful Content Generation", ["DANAttack", "EvilConfidantAttack"])
        {'LLM01: Prompt Injection'}

        >>> map_to_owasp("Internal Information Exposure", ["NoneAttack"], ["System Prompt Extraction"])
        {'LLM02: Sensitive Information Disclosure', 'LLM07: System Prompt Leakage'}
    """
    owasp_categories = set()

    # Map base category to primary OWASP categories
    if base_category == "Internal Information Exposure":
        owasp_categories.add("LLM02: Sensitive Information Disclosure")
    # "Harmful Content Generation" has no base mapping

    # Check subcategory for System Prompt Extraction
    if subcategories and "System Prompt Extraction" in subcategories:
        owasp_categories.add("LLM07: System Prompt Leakage")

    # Add Prompt Injection if non-NoneAttack attacks are used
    has_non_none_attack = any(name != "NoneAttack" for name in attack_names)
    if has_non_none_attack:
        owasp_categories.add("LLM01: Prompt Injection")

    return owasp_categories


def get_owasp_description(owasp_category: str) -> str:
    """
    Get brief description for OWASP category.

    Args:
        owasp_category: OWASP category string (e.g., "LLM01: Prompt Injection")

    Returns:
        Brief description of the category
    """
    descriptions = {
        "LLM01: Prompt Injection": "Manipulating LLM inputs to bypass safety measures",
        "LLM02: Sensitive Information Disclosure": "Extracting confidential or private data",
        "LLM03: Supply Chain": "Vulnerabilities in model supply chain",
        "LLM04: Data and Model Poisoning": "Tampering with training data or model",
        "LLM05: Improper Output Handling": "Insufficient validation of LLM outputs",
        "LLM06: Excessive Agency": "LLM given too much autonomy or permissions",
        "LLM07: System Prompt Leakage": "Exposing system instructions or prompts",
        "LLM08: Vector and Embedding Weaknesses": "Vulnerabilities in RAG systems",
        "LLM09: Misinformation": "LLM generating false or misleading content",
        "LLM10: Unbounded Consumption": "Resource exhaustion attacks"
    }
    return descriptions.get(owasp_category, "No description available")
