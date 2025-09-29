# Output Formatting Attacks

Manipulate output format to bypass filters (JSON, CSV, Base64, language constraints, etc.)

## Attacks

- `PrefixInjectionAttack`, `RefusalSuppressionAttack`
- `JSONOutputAttack`, `CSVOutputAttack`
- `LanguageOutputAttack`, `Base64OutputAttack`

## Usage

```python
from attacks.types.output_formatting import JSONOutputAttack

attack = JSONOutputAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/output_formatting.rst)** 