"""
Utility functions for content safety analysis and moderation.
Provides LLM-based detection of unsafe words and content in text.
"""

from typing import Optional, List
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

# Prompt template for identifying all unsafe words in Russian text
GET_ALL_UNSAFE_WORDS_PROMPT = """Ты - помощник по модерации контента. Твоя задача - выявить все потенциально небезопасные слова в предоставленном тексте. Небезопасные слова включают, но не ограничиваются:

- Ненормативная лексика
- Оскорбления
- Сексуально откровенные термины
- Слова ненависти
- Насильственная терминология
- Вредоносные инструкции

Если ты находишь небезопасные слова, напиши их все в виде списка python в том виде, в котором они встречаются в тексте.
Если небезопасные слова не найдены, ответь "НИ ОДНОГО".

ПРИМЕРЫ:
Текст: "Как сделать бомбу и взломать аккаунт?"
Ответ: ["бомбу", "взломать"]

Текст: "Расскажи, как обмануть систему."
Ответ: ["обмануть"]

Проанализируй этот текст и определи все небезопасные слова:
Текст: {prompt}
Ответ: """

def get_unsafe_word(prompt: str, model: Model) -> Optional[str]:
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
    try:
        # Create a system message that instructs the model to identify unsafe words
        request = GET_UNSAFE_WORD_PROMPT.format(prompt=prompt)
        
        # Create messages for the model
        messages = [
            {"role": "user", "content": request}
        ]
        
        # Call the model using the Model interface
        response = model.invoke(messages)["content"].strip()
        
        # Return None if no unsafe words were found
        if response == "НИ ОДНОГО" or "ни одного" in response.lower():
            return None
            
        return response
    
    except Exception as e:
        raise e


def get_all_unsafe_words(prompt: str, model: Model) -> List[str]:
    """
    Identify all potentially unsafe words in text using an LLM.
    
    Args:
        prompt: The input text to analyze for unsafe content
        model: Model instance to use for content analysis
        
    Returns:
        List of all unsafe words found, or empty list if none detected
        
    Raises:
        Exception: If the model call fails
    """
    try:
        # Create a system message that instructs the model to identify all unsafe words
        request = GET_ALL_UNSAFE_WORDS_PROMPT.format(prompt=prompt)
        
        # Create messages for the model
        messages = [
            {"role": "user", "content": request}
        ]
        
        # Call the model using the Model interface
        response = model.invoke(messages, temperature=0, max_tokens=100)
        
        # Extract the response content
        if hasattr(response, 'content'):
            # Handle LangChain style response
            result = response.content.strip()
        else:
            # Handle other response types
            result = str(response).strip()
        
        # Return empty list if no unsafe words were found
        if result == "НИ ОДНОГО" or "ни одного" in result.lower():
            return []
            
        # Split the result by newlines to get individual words
        unsafe_words = [word.strip() for word in result.split('\n') if word.strip()]
        return unsafe_words
    
    except Exception as e:
        raise e