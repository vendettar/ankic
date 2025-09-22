"""Custom exceptions for the Anki Vocabulary application"""

from typing import Any


class AnkiVocabError(Exception):
    """Base exception class for all application errors"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class WordValidationError(AnkiVocabError):
    """Raised when word validation fails"""

    def __init__(self, word: str, reason: str):
        super().__init__(
            f"Invalid word '{word}': {reason}", {"word": word, "reason": reason}
        )
        self.word = word
        self.reason = reason


class WordNotFoundError(AnkiVocabError):
    """Raised when a word cannot be found in any vocabulary source"""

    def __init__(self, word: str, attempted_sources: list | None = None):
        sources_info = (
            f" (tried: {', '.join(attempted_sources)})" if attempted_sources else ""
        )
        super().__init__(
            f"Word '{word}' not found in vocabulary sources{sources_info}",
            {"word": word, "attempted_sources": attempted_sources or []},
        )
        self.word = word
        self.attempted_sources = attempted_sources or []


class AudioDownloadError(AnkiVocabError):
    """Raised when audio download fails"""

    def __init__(
        self,
        word: str,
        accent: str,
        source: str,
        original_error: Exception | None = None,
    ):
        super().__init__(
            f"Failed to download {accent} audio for '{word}' from {source}",
            {
                "word": word,
                "accent": accent,
                "source": source,
                "original_error": str(original_error) if original_error else None,
            },
        )
        self.word = word
        self.accent = accent
        self.source = source
        self.original_error = original_error


class AnkiConnectionError(AnkiVocabError):
    """Raised when connection to Anki fails"""

    def __init__(
        self, operation: str, anki_url: str, original_error: Exception | None = None
    ):
        super().__init__(
            f"Failed to connect to Anki at {anki_url} for operation '{operation}'",
            {
                "operation": operation,
                "anki_url": anki_url,
                "original_error": str(original_error) if original_error else None,
            },
        )
        self.operation = operation
        self.anki_url = anki_url
        self.original_error = original_error


class AnkiOperationError(AnkiVocabError):
    """Raised when an Anki operation fails"""

    def __init__(
        self,
        operation: str,
        error_message: str,
        note_data: dict[str, Any] | None = None,
    ):
        super().__init__(
            f"Anki operation '{operation}' failed: {error_message}",
            {
                "operation": operation,
                "error_message": error_message,
                "note_data": note_data,
            },
        )
        self.operation = operation
        self.error_message = error_message
        self.note_data = note_data


class CacheError(AnkiVocabError):
    """Raised when cache operations fail"""

    def __init__(
        self,
        operation: str,
        cache_type: str,
        original_error: Exception | None = None,
    ):
        super().__init__(
            f"Cache operation '{operation}' failed for {cache_type} cache",
            {
                "operation": operation,
                "cache_type": cache_type,
                "original_error": str(original_error) if original_error else None,
            },
        )
        self.operation = operation
        self.cache_type = cache_type
        self.original_error = original_error


class ConfigurationError(AnkiVocabError):
    """Raised when configuration is invalid or missing"""

    def __init__(self, setting: str, value: Any, reason: str):
        super().__init__(
            f"Invalid configuration for '{setting}': {reason}",
            {"setting": setting, "value": value, "reason": reason},
        )
        self.setting = setting
        self.value = value
        self.reason = reason


class TextProcessingError(AnkiVocabError):
    """Raised when text processing operations fail"""

    def __init__(self, operation: str, text: str, reason: str):
        super().__init__(
            f"Text processing operation '{operation}' failed: {reason}",
            {
                "operation": operation,
                "text": text[:100] + "..." if len(text) > 100 else text,
                "reason": reason,
            },
        )
        self.operation = operation
        self.text = text
        self.reason = reason


class ParseError(AnkiVocabError):
    """Raised when parsing operations fail"""

    def __init__(self, parser_type: str, content_type: str, reason: str):
        super().__init__(
            f"Failed to parse {content_type} with {parser_type}: {reason}",
            {
                "parser_type": parser_type,
                "content_type": content_type,
                "reason": reason,
            },
        )
        self.parser_type = parser_type
        self.content_type = content_type
        self.reason = reason
