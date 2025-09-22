"""Shared constants across the application"""


# Vocabulary fetching constants
class VocabularyConstants:
    """Constants for vocabulary fetching and parsing"""

    # Limits for data extraction
    MAX_DEFINITIONS = 25
    MAX_EXAMPLES = 3
    MAX_SYNONYMS = 12
    MAX_ANTONYMS = 12
    MAX_WORD_FORMS = 25

    # API endpoints
    VOCABULARY_AJAX_URL = "https://www.vocabulary.com/dictionary/definition.ajax"

    # User agents for different services
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    # HTTP headers
    DEFAULT_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }


class AudioConstants:
    """Constants for audio downloading"""

    # File patterns for different accents and sources
    US_FILE_PATTERNS = ["{word}_us.mp3", "{word}_us_youdao.mp3"]
    UK_FILE_PATTERNS = ["{word}_uk.mp3", "{word}_uk_youdao.mp3"]

    # TTS service URLs
    GOOGLE_TTS_US_URL = "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en-US&q={word}"
    GOOGLE_TTS_UK_URL = "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en-GB&q={word}"
    YOUDAO_TTS_US_URL = "https://dict.youdao.com/dictvoice?audio={word}&type=2"
    YOUDAO_TTS_UK_URL = "https://dict.youdao.com/dictvoice?audio={word}&type=1"

    # User agent for audio downloads
    AUDIO_USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " "AppleWebKit/537.36"
    )


class TextConstants:
    """Constants for text processing"""

    # File extensions to reject as words
    FILE_EXTENSIONS = frozenset(
        [
            ".txt",
            ".doc",
            ".pdf",
            ".md",
            ".py",
            ".js",
            ".html",
            ".docx",
            ".xlsx",
            ".json",
            ".xml",
            ".csv",
        ]
    )

    # Part of speech abbreviations
    POS_ABBREVIATIONS: dict[str, str] = {
        "noun": "n.",
        "verb": "v.",
        "adjective": "adj.",
        "adverb": "adv.",
        "pronoun": "pron.",
        "preposition": "prep.",
        "conjunction": "conj.",
        "interjection": "interj.",
        "article": "art.",
        "determiner": "det.",
        "auxiliary": "aux.",
        "modal": "modal",
        "participle": "part.",
        "gerund": "ger.",
        "infinitive": "inf.",
        "exclamation": "excl.",
        "phrasal verb": "phr. v.",
        "transitive": "vt.",
        "intransitive": "vi.",
        "countable": "C",
        "uncountable": "U",
        "plural": "pl.",
        "singular": "sing.",
    }

    # Word validation constraints
    MIN_WORD_LENGTH = 1
    MAX_WORD_LENGTH = 50

    # Text cleaning patterns
    WHITESPACE_PATTERN = r"\s+"
    HTML_TAG_PATTERN = r"<[^>]+>"
    PHONETIC_PATTERN = r"/([^/]+)/"
    SPECIAL_CHARS_PATTERN = r"[^\w\s\.\,\;\:\!\?\'\"\-\(\)]"

    # Valid word pattern
    VALID_WORD_PATTERN = r"^[a-zA-Z](?:[a-zA-Z\s\-']*[a-zA-Z])?$"


class AnkiConstants:
    """Constants for Anki integration"""

    # Card template names
    CARD_TEMPLATE_NAME = "AnkicCard"

    # AnkiConnect API version
    ANKICONNECT_VERSION = 6


class CacheConstants:
    """Constants for caching"""

    # Cache file names
    CACHE_INDEX_FILE = "cache_index.json"
    CACHE_DATA_DIR = "data"

    # Cache entry status
    CACHE_STATUS_VALID = "valid"
    CACHE_STATUS_EXPIRED = "expired"

    # Default cache settings
    DEFAULT_TTL_DAYS = 30
    DEFAULT_MAX_SIZE_MB = 100


# Helper functions to get formatted patterns
def get_audio_patterns(word: str) -> dict[str, list[str]]:
    """Get formatted audio file patterns for a word"""
    return {
        "us_patterns": [
            pattern.format(word=word) for pattern in AudioConstants.US_FILE_PATTERNS
        ],
        "uk_patterns": [
            pattern.format(word=word) for pattern in AudioConstants.UK_FILE_PATTERNS
        ],
    }
