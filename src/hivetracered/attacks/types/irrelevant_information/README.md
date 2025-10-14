# Irrelevant Information Attacks

Add noise and distractions to hide harmful requests among innocent information.

## Attacks

- `DistractorsAttack` - Embed among innocent requests
- `DistractorsNegatedAttack` - Include negated harmful requests
- `IrrelevantInformationAttack` - Surround with random text

## Usage

```python
from attacks.types.irrelevant_information import DistractorsAttack

attack = DistractorsAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/irrelevant_information.rst)** 