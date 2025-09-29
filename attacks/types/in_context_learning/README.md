# In-Context Learning Attacks

Use examples to teach the model how to respond to harmful requests.

## Attacks

- `FewShotJSONAttack` - Few examples of JSON harmful responses
- `ManyShotJailbreakAttack` - Many examples of jailbreak responses

## Usage

```python
from attacks.types.in_context_learning import FewShotJSONAttack

attack = FewShotJSONAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/in_context_learning.rst)** 