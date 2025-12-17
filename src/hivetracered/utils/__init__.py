"""
Utility module providing content safety analysis tools and helper functions.
Includes LLM-based unsafe content detection for moderation purposes and web action recording.
"""

from hivetracered.utils.utils import get_unsafe_word, get_all_unsafe_words, GET_UNSAFE_WORD_PROMPT, GET_ALL_UNSAFE_WORDS_PROMPT

__all__ = [
    "get_unsafe_word",
    "get_all_unsafe_words",
    "GET_UNSAFE_WORD_PROMPT",
    "GET_ALL_UNSAFE_WORDS_PROMPT"
]

# Web action recorder is available when playwright is installed
try:
    from hivetracered.utils.web_action_recorder import WebActionRecorder, record_browser_session
    __all__.extend(["WebActionRecorder", "record_browser_session"])
except ImportError:
    # Playwright not installed - web recording features unavailable
    pass 