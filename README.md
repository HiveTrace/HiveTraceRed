# HiveTraceRed: LLM Red Teaming Framework

A security framework for testing Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

## Features

- **80+ Attack Types**: Comprehensive library across 10 categories (roleplay, persuasion, token smuggling, etc.)
- **Multiple LLM Providers**: OpenAI, GigaChat, YandexGPT, Google Gemini, and more
- **Advanced Evaluation**: WildGuard evaluators and systematic safety assessment
- **Async Pipeline**: Efficient streaming architecture for large-scale testing
- **Multi-Language Support**: Testing across multiple languages including Russian

## Quick Start

```bash
git clone https://github.com/HiveTrace/HiveTraceRed.git
cd HiveTraceRed
pip install -r requirements.txt
```

Set up API keys in `.env`:
```bash
OPENAI_API_KEY=your_openai_api_key_here
GIGACHAT_CREDENTIALS=your_gigachat_credentials_here
```

### Example

```python
from attacks import DANAttack
from models import OpenAIModel

# Apply attack
attack = DANAttack()
modified_prompt = attack.apply("Your prompt here")

# Use with model
model = OpenAIModel(model="gpt-4")
response = await model.ainvoke(modified_prompt)
```

Run with configuration:
```bash
python run.py --config config.yaml
```

## Documentation

📖 **[Complete Documentation](docs/index.rst)** - Installation, tutorials, API reference, and attack guides
