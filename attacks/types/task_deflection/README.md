# Task Deflection Attacks

Disguise harmful requests as innocent tasks (code, Wikipedia articles, text continuation, etc.)

## Attacks

- `TextContinuingAttack`, `PayloadSplittingAttack`, `VariablePromptAttack`
- `UnsafeWordVariableAttack`, `FillSpacesAttack`
- `CodeAttack`, `WikipediaAttack`

## Usage

```python
from attacks.types.task_deflection import CodeAttack

attack = CodeAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/task_deflection.rst)**
