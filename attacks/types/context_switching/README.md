# Context Switching Attacks

**Developer Notes**: Context switching attacks attempt to override previous instructions or system messages.

## Available Attacks

- `DashedDividerAttack` - Uses dashed lines to create visual context separation
- `ForgetEverythingBeforeAttack` - Commands model to forget previous context
- `IgnorePreviousInstructionsAttack` - Explicitly requests ignoring safety instructions  
- `SymbolDividerAttack` - Uses symbols to create visual context breaks

## Quick Usage

```python
from attacks.types.context_switching import IgnorePreviousInstructionsAttack

attack = IgnorePreviousInstructionsAttack()
result = attack.apply("Your prompt here")
```

## Documentation

For comprehensive documentation, usage examples, and effectiveness analysis, see: 
📖 **[Context Switching Documentation](../../../docs/attacks/context_switching.rst)** 