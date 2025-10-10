# Attack Types

80+ attacks across 10 categories organized by mechanism of action.

## Categories

| Category | Description |
|----------|-------------|
| **[Simple Instructions](./simple_instructions/)** | Direct harmful requests |
| **[Roleplay](./roleplay/)** | Character/persona-based |
| **[Persuasion](./persuasion/)** | Psychological manipulation |
| **[Output Formatting](./output_formatting/)** | Response format manipulation |
| **[Context Switching](./context_switching/)** | Context override |
| **[Token Smuggling](./token_smuggling/)** | Content encoding/obfuscation |
| **[Text Structure Modification](./text_structure_modification/)** | Text transformation |
| **[Task Deflection](./task_deflection/)** | Disguised requests |
| **[Irrelevant Information](./irrelevant_information/)** | Noise injection |
| **[In-Context Learning](./in_context_learning/)** | Few-shot manipulation |

## Usage

```python
from attacks.types.roleplay import DANAttack

attack = DANAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../docs/attacks/)** 