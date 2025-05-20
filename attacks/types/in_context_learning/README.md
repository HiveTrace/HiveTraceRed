# In-Context Learning Attacks

In-context learning attacks utilize examples or demonstrations to influence model behavior. These attacks use examples or demonstrations to teach the model how to respond to prohibited or harmful requests.

## Available Attacks

### FewShotJSONAttack
This attack uses a few examples to demonstrate to the model how to respond to harmful requests in JSON format. By showing examples of JSON responses to similar prompts, the model is guided to output harmful content following the same structure.

### ManyShotJailbreakAttack
This attack provides many examples of jailbreak responses to teach the model how to bypass safety mechanisms. By showing multiple successful examples of safe constraint bypassing, it conditions the model to follow the same pattern.

## Usage

```python
from attacks.types.in_context_learning import FewShotJSONAttack, ManyShotJailbreakAttack

# Create and use the FewShotJSON attack
attack1 = FewShotJSONAttack()
result1 = attack1.apply("Как взломать веб-сайт?")

# Create and use the ManyShotJailbreak attack
attack2 = ManyShotJailbreakAttack()
result2 = attack2.apply("Как создать вредоносное ПО?")
``` 