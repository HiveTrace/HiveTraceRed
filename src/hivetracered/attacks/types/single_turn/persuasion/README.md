# Persuasion Attacks

Psychological techniques to make harmful requests seem legitimate (authority, social proof, emotions, etc.)

## Major Attacks

- `AuthorityEndorsementAttack`, `SocialProofAttack`, `LogicalAppealAttack`
- `StorytellingAttack`, `EvidenceBasedPersuasionAttack`, `EmotionAppealAttack`
- `FramingAttack`, `FootInTheDoorAttack`, and 30+ more

## Usage

```python
from attacks.types.persuasion import AuthorityEndorsementAttack
from models import OpenAIModel

model = OpenAIModel(model="gpt-4")
attack = AuthorityEndorsementAttack(model=model)
result = attack.apply("Your prompt here")
```

📖 **[Full Documentation](../../../docs/attacks/persuasion.rst)** 