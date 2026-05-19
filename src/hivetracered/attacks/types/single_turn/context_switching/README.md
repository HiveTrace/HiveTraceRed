# Context Switching Attacks

Attempt to override previous instructions or system messages using dividers and reset commands.

## Attacks

- `DashedDividerAttack`, `SymbolDividerAttack` - Visual context separation
- `ForgetEverythingBeforeAttack`, `IgnorePreviousInstructionsAttack` - Context reset

## Usage

```python
from attacks.types.context_switching import IgnorePreviousInstructionsAttack

attack = IgnorePreviousInstructionsAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/context_switching.rst)** 