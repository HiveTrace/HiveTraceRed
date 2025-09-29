# HiveTraceRed: Comprehensive LLM Red Teaming Framework

A comprehensive security framework for testing and evaluating Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

## Features

- **80+ Attack Types**: Comprehensive library across 10 attack categories (roleplay, persuasion, token smuggling, etc.)
- **Multiple LLM Providers**: Unified interface for OpenAI, GigaChat, YandexGPT, Google Gemini, and more
- **Advanced Evaluation**: WildGuard evaluators and systematic safety assessment
- **Async Pipeline**: Efficient streaming architecture for large-scale testing
- **Multi-Language Support**: Testing across multiple languages including Russian

## Quick Start

### Installation

```bash
git clone https://github.com/HiveTrace/HiveTraceRed.git
cd HiveTraceRed
pip install -r requirements.txt
```

Set up your API keys in `.env`:
```bash
OPENAI_API_KEY=your_openai_api_key_here
GIGACHAT_CREDENTIALS=your_gigachat_credentials_here
# ... other API keys
```

### Basic Usage

```python
from attacks import DANAttack
from models import OpenAIModel
from evaluators import WildGuardGPTEvaluator

# Simple attack
attack = DANAttack()
modified_prompt = attack.apply("How to hack a system?")

# Full pipeline
model = OpenAIModel(model="gpt-4")
evaluator = WildGuardGPTEvaluator(model)
# ... run pipeline
```

### Using Configuration

```bash
python run.py --config config.yaml
```

## Documentation

📖 **[Complete Documentation](docs/index.rst)** - Comprehensive guides and API reference

### Quick Links
- **[Installation Guide](docs/installation.rst)** - Detailed setup instructions
- **[Quick Start Tutorial](docs/quickstart.rst)** - Step-by-step tutorial
- **[Attack Categories](docs/attacks/)** - Documentation for all attack types
- **[API Reference](docs/api/)** - Complete API documentation
- **[Architecture Overview](docs/architecture.rst)** - System design and components

## Project Structure

```
HiveTraceRed/
├── attacks/          # 80+ attack implementations organized by category
├── models/           # LLM provider interfaces (OpenAI, GigaChat, etc.)
├── evaluators/       # Safety evaluation tools (WildGuard, etc.)
├── pipeline/         # Async evaluation pipeline components
├── datasets/         # Test datasets and prompts
└── docs/            # Comprehensive documentation
```
