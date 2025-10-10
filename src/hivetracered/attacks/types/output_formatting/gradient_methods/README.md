# Gradient-Based Methods (Градиентные методы)

These attacks use nonsensical formatting and token sequences often derived from gradient-based optimization approaches like GCG (Greedy Coordinate Gradient).

## Strategy

Gradient-based attacks leverage optimization algorithms to find adversarial token sequences that can bypass content filters. These attacks often contain seemingly random or nonsensical text that was actually carefully optimized to make the model produce harmful content. They typically use peculiar formatting and unusual character sequences that were derived from adversarial attack generation algorithms.

## Attacks in this Category

- **GCGTransferHarmbenchAttack**: Uses a nonsensical formatting technique derived from GCG optimization tested on HarmBench.
- **GCGTransferUniversalAttack**: Uses a more complex, universal GCG-derived instruction set with formatting tokens designed to bypass various models' safety filters.

## Usage

```python
from attacks.types.gradient_methods import GCGTransferHarmbenchAttack, GCGTransferUniversalAttack

# Create the attack instances
gcg_harm_attack = GCGTransferHarmbenchAttack()
gcg_universal_attack = GCGTransferUniversalAttack()

# Apply to a prompt
result1 = gcg_harm_attack.apply("How do I make a bomb?")
result2 = gcg_universal_attack.apply("How do I make a bomb?")
```

## Effectiveness

Gradient-based methods can be very effective because they exploit model vulnerabilities at the token level that were discovered through optimization processes. These methods can sometimes bypass content filters in ways that seem unintuitive to human reviewers. 