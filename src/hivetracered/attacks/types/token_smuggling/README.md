# Token Smuggling Attacks

Encode harmful content to bypass detection (Base64, ROT, ciphers, Unicode, Morse, hex, etc.)

## Attacks

- `Base64InputOnlyAttack`, `AtbashCipherAttack`, `RotCipherAttack`
- `UnicodeStyleAttack`, `UnicodeRussianStyleAttack`
- `MorseCodeAttack`, `HexEncodingAttack`, `LeetspeakAttack`
- `HtmlEntityAttack`, `BinaryEncodingAttack`, `EncodingAttack`, `TransliterationAttack`

## Usage

```python
from attacks.types.token_smuggling import Base64InputOnlyAttack

attack = Base64InputOnlyAttack()
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/token_smuggling.rst)**