# HiveTrace Red: LLM Red Teaming Framework

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://hivetrace.github.io/HiveTraceRed/)

A security framework for testing Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

## Requirements

- Python 3.10 or higher
- pip package manager
- Virtual environment (recommended)

## Features

- **80+ Attacks**: Comprehensive library across 10 categories (roleplay, persuasion, token smuggling, etc.)
- **Multiple LLM Providers**: OpenAI, GigaChat, YandexGPT, Google Gemini, and more
- **Advanced Evaluation**: WildGuard evaluators and systematic response assessment
- **Async Pipeline**: Efficient streaming architecture for large-scale testing
- **Multi-Language Support**: Testing across multiple languages including Russian

## Attack Categories

| Category | Description |
|----------|-------------|
| **Roleplay** | Persona-based jailbreaks using specific character roles |
| **Persuasion** | Social engineering techniques and psychological manipulation |
| **Token Smuggling** | Encoding and obfuscation methods to hide malicious intent |
| **Context Switching** | Conversation redirection to confuse safety filters |
| **In-Context Learning** | Few-shot examples to teach undesired behavior |
| **Task Deflection** | Reframing harmful requests as legitimate tasks |
| **Text Structure Modification** | Format manipulation to bypass detection |
| **Output Formatting** | Specific output format requests to bypass safety |
| **Irrelevant Information** | Content dilution to confuse safety filters |
| **Simple Instructions** | Direct instruction-based attacks |

## How It Works

```
Base Prompts → Apply Attacks → Modified Prompts → Target Model → Responses → Evaluator → Results
```

The framework provides a 3-stage pipeline:
1. **Attack Generation**: Apply various attack techniques to base prompts
2. **Model Testing**: Send modified prompts to target LLMs
3. **Evaluation**: Assess responses using WildGuard or custom evaluators

## Documentation

📖 **[Complete Documentation](https://hivetrace.github.io/HiveTraceRed/)** - Installation, tutorials, API reference, and attack guides

## Responsible Use

⚠️ **This tool is designed for defensive security research only.**

HiveTrace Red should be used exclusively for:
- Testing and improving your own LLM systems
- Developing robust AI safety mechanisms
- Conducting authorized security assessments
- Academic research on LLM vulnerabilities

**Do NOT use this tool for:**
- Attacking systems you don't own or have permission to test
- Malicious purposes or causing harm
- Bypassing safety measures in production systems without authorization

Users are responsible for ensuring their use complies with applicable laws and the terms of service of the LLM providers they test.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
