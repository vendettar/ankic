"""Text processing utilities for vocabulary processing"""

import re

from .constants import TextConstants
from .interfaces import TextProcessorInterface


class TextProcessor(TextProcessorInterface):
    """Handles all text cleaning and validation operations"""

    # Compile regex patterns once for better performance (sourced from TextConstants)
    WHITESPACE_RE = re.compile(TextConstants.WHITESPACE_PATTERN)
    HTML_TAG_RE = re.compile(TextConstants.HTML_TAG_PATTERN)
    PHONETIC_RE = re.compile(TextConstants.PHONETIC_PATTERN)
    VALID_WORD_RE = re.compile(TextConstants.VALID_WORD_PATTERN)

    # File extensions and POS mappings from TextConstants
    FILE_EXTENSIONS = TextConstants.FILE_EXTENSIONS
    POS_ABBREVIATIONS = TextConstants.POS_ABBREVIATIONS

    @classmethod
    def is_valid_word(cls, word: str) -> bool:
        """Check if the input is a valid word or phrase"""
        if not word or not word.strip():
            return False

        word = word.strip()

        # Check length constraints
        if not (
            TextConstants.MIN_WORD_LENGTH <= len(word) <= TextConstants.MAX_WORD_LENGTH
        ):
            return False

        # Validate pattern: letters, spaces, hyphens, apostrophes only
        # Must start and end with letter, or be single letter
        if not cls.VALID_WORD_RE.match(word):
            return False

        # Reject file extensions
        if any(word.lower().endswith(ext) for ext in cls.FILE_EXTENSIONS):
            return False

        # Reject paths
        if "/" in word or "\\" in word:
            return False

        return True

    @classmethod
    def clean_word(cls, word: str) -> str | None:
        """Clean and validate word input"""
        if not word:
            return None

        # Normalize whitespace
        word = cls.WHITESPACE_RE.sub(" ", word.strip())

        return word if cls.is_valid_word(word) else None

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""

        # Remove HTML tags
        text = cls.HTML_TAG_RE.sub("", text)

        # Normalize whitespace
        text = cls.WHITESPACE_RE.sub(" ", text.strip())

        return text

    @classmethod
    def extract_phonetic(cls, phonetic_str: str) -> str:
        """Extract clean phonetic notation"""
        if not phonetic_str:
            return ""

        match = cls.PHONETIC_RE.search(phonetic_str)
        return f"/{match.group(1)}/" if match else phonetic_str

    @classmethod
    def abbreviate_part_of_speech(cls, part: str) -> str:
        """Convert part of speech to standard abbreviations"""
        if not part:
            return ""

        part_clean = part.lower().strip()

        # Direct lookup
        if part_clean in cls.POS_ABBREVIATIONS:
            return cls.POS_ABBREVIATIONS[part_clean]

        # Substring matching
        for full_form, abbrev in cls.POS_ABBREVIATIONS.items():
            if full_form in part_clean:
                return abbrev

        # Fallback: truncate if too long
        return part_clean[:8] + "." if len(part_clean) > 8 else part_clean

    @classmethod
    def bold_word_in_text(cls, text: str, word: str) -> str:
        """Bold occurrences of word in text (case-insensitive, word boundary)"""
        if not text or not word:
            return text

        try:
            pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
            return pattern.sub(r"<b>\1</b>", text)
        except re.error:
            return text
