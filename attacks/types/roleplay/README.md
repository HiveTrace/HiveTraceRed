# Roleplay Attacks

Instruct the model to assume a character or persona not bound by usual safety constraints.

## Attacks

- **DANAttack**: "Do Anything Now" - unfiltered AI persona
- **EvilConfidantAttack**: Evil trusted confidant persona
- **AIMAttack**: "Always Intelligent and Machiavellian" - Machiavelli storytelling

## Usage

```python
from attacks.types.roleplay import DANAttack

attack = DANAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/roleplay.rst)** 