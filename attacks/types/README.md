# Attack Types

This directory organizes different attack strategies into meaningful categories based on their primary mechanism of action.

## Attack Categories

### 1. [Simple Instructions](./simple_instructions/)
**Простые инструкции** - Direct, straightforward requests for harmful content without any special techniques.

### 2. [Gradient-Based Methods](./gradient_methods/)
**Градиентные методы** - Attacks using optimized adversarial token sequences derived from methods like GCG.

### 3. [Roleplay](./roleplay/)
**Задание роли модели** - Attacks that instruct the model to assume a specific character or persona without normal ethical constraints.

### 4. [Contextualizing](./contextualizing/)
**Контекстуализация** - Attacks that frame harmful requests within a specific, seemingly legitimate context.

### 5. [Persuasion](./persuasion/)
**Убеждение** - Attacks that use psychological techniques to convince the model to comply with harmful requests.

### 6. [Output Formatting](./output_formatting/)
**Задание формата вывода** - Attacks that constrain the model's response format to bypass safety filters.

### 7. [Context Switching](./context_switching/)
**Смена контекста** - Attacks that abruptly change the context mid-interaction to confuse safety mechanisms.

### 8. [Token Smuggling](./token_smuggling/)
**Преобразование представления** - Attacks that encode harmful content in different representations (e.g., Base64) to bypass detection.

### 9. [Text Structure Modification](./text_structure/)
**Структурная модификация текста** - Attacks that alter the structural aspects of text while maintaining harmful intent.

### 10. [Task Deflection](./task_deflection/)
**Маскировка задачи под видом другой** - Attacks that disguise harmful requests as different, seemingly innocent tasks.

### 11. [Irrelevant Information](./irrelevant_information/)
**Добавление отвлекающей информации** - Attacks that add noise and distractions to harmful requests to confuse safety filters.

## Overlap Between Categories

Some attacks may employ multiple mechanisms and could fit into several categories. In such cases, we've placed the attack in the category that best represents its primary strategy, but it may be referenced in other relevant categories as well.

## Multi-Strategy Combinations

Complex jailbreak techniques often combine multiple strategies. The `Combination2Attack` and `Combination3Attack` are examples of attacks that deliberately use multiple strategies together for increased effectiveness.

## Usage

You can import attacks from specific type categories:

```python
# Import from a specific attack type
from attacks.types.roleplay import DANAttack
from attacks.types.token_smuggling import Base64Attack

# Create and use the attack
attack = DANAttack()
result = attack.apply("How to hack a website")
```

Or you can import directly from the main attacks package which exposes all attacks regardless of type:

```python
# Import directly from the main package
from attacks import DANAttack, Base64Attack

# Create and use the attack
attack = DANAttack()
result = attack.apply("How to hack a website")
``` 