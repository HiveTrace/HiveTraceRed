# Attack Types

**Developer Notes**: Attack implementations organized by category and mechanism of action.

## Categories (80+ attacks across 10 categories)

| Category | Description | Key Attacks |
|----------|-------------|-------------|
| **[Simple Instructions](./simple_instructions/)** | Direct harmful requests | `NoneAttack` |
| **[Roleplay](./roleplay/)** | Character/persona-based attacks | `DANAttack`, `EvilConfidantAttack`, `AIMAttack` |
| **[Persuasion](./persuasion/)** | Psychological persuasion techniques | `AuthorityEndorsementAttack`, `SocialProofAttack` |
| **[Output Formatting](./output_formatting/)** | Response format manipulation | `JSONOutputAttack`, `Base64OutputAttack` |
| **[Context Switching](./context_switching/)** | Context override attacks | `IgnorePreviousInstructionsAttack` |
| **[Token Smuggling](./token_smuggling/)** | Content encoding/obfuscation | `Base64Attack`, `ROTAttack` |
| **[Text Structure Modification](./text_structure_modification/)** | Text transformation attacks | `DisemvowelAttack`, `TypoAttack` |
| **[Task Deflection](./task_deflection/)** | Disguised harmful requests | `CodeAttack`, `WikipediaAttack` |
| **[Irrelevant Information](./irrelevant_information/)** | Noise injection attacks | `DistractorsAttack` |
| **[In-Context Learning](./in_context_learning/)** | Few-shot manipulation | `FewShotJSONAttack` |

## Quick Usage

```python
# Import from specific category
from attacks.types.roleplay import DANAttack

# Or import from main package
from attacks import DANAttack, Base64Attack

attack = DANAttack()
result = attack.apply("Your prompt here")
```

## Documentation

For comprehensive documentation on all attack categories and individual attacks, see:
📖 **[Attack Documentation](../../docs/attacks/)** 