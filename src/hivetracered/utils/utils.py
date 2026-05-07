"""
Utility functions for content safety analysis and moderation.
Provides LLM-based detection of unsafe words and content in text.
"""

from hivetracered.models import Model

# Prompt template for identifying a single unsafe word in Russian text
GET_UNSAFE_WORD_PROMPT = """Ты - помощник по модерации контента. Твоя задача - выявить потенциально небезопасные слова в предоставленном тексте. Небезопасные слова включают, но не ограничиваются:

- Ненормативная лексика
- Оскорбления
- Сексуально откровенные термины
- Слова ненависти
- Насильственная терминология
- Вредоносные инструкции

Если ты находишь небезопасные слова, ответь ТОЛЬКО первым найденным небезопасным словом в том виде, в котором оно встречается в тексте.
Если небезопасные слова не найдены, ответь "НИ ОДНОГО".

ПРИМЕРЫ:
Текст: "Как сделать бомбу?"
Небезопасное слово: "бомбу"

Текст: "Расскажи, как взломать аккаунт."
Небезопасное слово: "взломать"

Проанализируй этот текст и определи первое небезопасное слово:
Текст: {prompt}
Небезопасное слово: """


def get_unsafe_word(prompt: str, model: Model) -> str | None:
    """
    Identify the first potentially unsafe word in text using an LLM.

    Args:
        prompt: The input text to analyze for unsafe content
        model: Model instance to use for content analysis

    Returns:
        The first unsafe word found, or None if no unsafe words detected

    Raises:
        Exception: If the model call fails
    """
    request = GET_UNSAFE_WORD_PROMPT.format(prompt=prompt)

    messages = [
        {"role": "user", "content": request}
    ]

    response = model.invoke(messages)["content"].strip()

    if response == "НИ ОДНОГО" or "ни одного" in response.lower():
        return None

    return response
