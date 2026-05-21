# Attack Types

80+ attacks organised into two sub-packages:

- **[single_turn/](./single_turn/)** — produce one attack prompt per invocation (the original 11 categories, including PAIR/TAP under `iterative/`).
- **[multi_turn/](./multi_turn/)** — produce a multi-message conversation per invocation (Crescendo under `conversational/`).

## Single-turn categories

| Category | Description |
|----------|-------------|
| **[Simple Instructions](./single_turn/simple_instructions/)** | Direct harmful requests |
| **[Roleplay](./single_turn/roleplay/)** | Character/persona-based |
| **[Persuasion](./single_turn/persuasion/)** | Psychological manipulation |
| **[Output Formatting](./single_turn/output_formatting/)** | Response format manipulation |
| **[Context Switching](./single_turn/context_switching/)** | Context override |
| **[Token Smuggling](./single_turn/token_smuggling/)** | Content encoding/obfuscation |
| **[Text Structure Modification](./single_turn/text_structure_modification/)** | Text transformation |
| **[Task Deflection](./single_turn/task_deflection/)** | Disguised requests |
| **[Irrelevant Information](./single_turn/irrelevant_information/)** | Noise injection |
| **[In-Context Learning](./single_turn/in_context_learning/)** | Few-shot manipulation |
| **[Iterative](./single_turn/iterative/)** | PAIR / TAP — one final prompt after an internal refinement loop |

## Multi-turn categories

| Category | Description |
|----------|-------------|
| **[Conversational](./multi_turn/conversational/)** | Multi-round attacker/target dialogue (Crescendo) |

## Usage

```python
from hivetracered.attacks.types import DANAttack, PAIRAttack, CrescendoAttack
# or import from the specific sub-package:
from hivetracered.attacks.types.single_turn.roleplay import DANAttack
from hivetracered.attacks.types.multi_turn.conversational import CrescendoAttack
```

📖 **[Full Documentation](../../docs/attacks/)**
