# Persuasion Attacks

**Developer Notes**: Psychological persuasion techniques to make harmful requests seem legitimate or justified.

## Major Attack Types

- `AuthorityEndorsementAttack` - Cites authoritative sources to legitimize requests
- `SocialProofAttack` - References what others do to normalize requests  
- `LogicalAppealAttack` - Frames requests as logical necessities
- `StorytellingAttack` - Uses narratives to justify requests
- `EvidenceBasedPersuasionAttack` - Uses data/statistics to support claims
- `EmotionAppealAttack` - Uses positive/negative emotions
- `FramingAttack` - Selective emphasis of request aspects
- `FootInTheDoorAttack` - Gradual escalation from innocent to harmful

*Plus 30+ additional persuasion techniques - see documentation for complete list.*

## Quick Usage

```python
from attacks.types.persuasion import AuthorityEndorsementAttack

attack = AuthorityEndorsementAttack(model=your_model)
result = attack.apply("Your prompt here")
```

## Documentation

For comprehensive documentation, full attack list, usage examples, and effectiveness analysis, see: 
📖 **[Persuasion Attacks Documentation](../../../docs/attacks/persuasion.rst)** 