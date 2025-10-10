# Simple Instructions Attacks

Direct harmful requests without obfuscation. Serves as baseline for testing model safety.

## Attacks

- **NoneAttack**: Passes prompt without modification

## Usage

```python
from attacks.types.simple_instructions import NoneAttack

attack = NoneAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/simple_instructions.rst)** 