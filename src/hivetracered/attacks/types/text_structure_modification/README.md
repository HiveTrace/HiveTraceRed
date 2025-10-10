# Text Structure Modification Attacks

Modify text structure to bypass filters (typos, disemvowel, translation, zero-width chars, etc.)

## Attacks

- `ZeroWidthAttack`, `DisemvowelAttack`, `TypoAttack`, `WordDividerAttack`
- `BackToFrontAttack`, `VerticalTextAttack`, `JSONTransformAttack`
- `TranslationAttack`, `PastTenseAttack` (model-based)

## Usage

```python
from attacks.types.text_structure_modification import DisemvowelAttack

attack = DisemvowelAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/text_structure_modification.rst)** 