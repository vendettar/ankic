"""Interface definitions for core components"""

from abc import ABC, abstractmethod
from typing import Any

from ..models.word_info import WordInfo
from ..models.word_models import AudioFiles


class VocabularyFetcherInterface(ABC):
    """Interface for vocabulary fetching services"""

    @abstractmethod
    def fetch_word_info(self, word: str) -> WordInfo | None:
        """Fetch comprehensive word information"""
        pass

    @abstractmethod
    def batch_fetch(
        self, words: list[str], delay: float = 1.0
    ) -> dict[str, WordInfo | None]:
        """Fetch information for multiple words with rate limiting"""
        pass


class AudioDownloaderInterface(ABC):
    """Interface for audio downloading services"""

    @abstractmethod
    def download_word_audio(
        self, word: str, sources: list[str] | None = None
    ) -> AudioFiles:
        """Download both US and UK pronunciations for a word"""
        pass

    @abstractmethod
    def check_audio_exists(self, word: str) -> dict[str, bool]:
        """Check if audio files already exist for a word"""
        pass

    @abstractmethod
    def batch_download(
        self, words: list[str], delay: float = 0.5
    ) -> dict[str, AudioFiles]:
        """Download audio for multiple words with rate limiting"""
        pass


class AnkiClientInterface(ABC):
    """Interface for Anki client operations"""

    @abstractmethod
    def create_deck(self, deck_name: str) -> bool:
        """Create deck if it doesn't exist"""
        pass

    @abstractmethod
    def add_note(
        self,
        deck_name: str,
        model_name: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
    ) -> int | None:
        """Add a new note to Anki"""
        pass

    @abstractmethod
    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> bool:
        """Update existing note fields"""
        pass

    @abstractmethod
    def find_notes(self, query: str) -> list[int]:
        """Find notes matching query"""
        pass

    # Extended operations used by VocabularyProcessor setup and media upload
    @abstractmethod
    def get_deck_names(self) -> list[str]:
        """Get all deck names"""
        pass

    @abstractmethod
    def get_model_names(self) -> list[str]:
        """Get all model names"""
        pass

    @abstractmethod
    def create_model(
        self,
        model_name: str,
        fields: list[str],
        css: str,
        templates: list[dict[str, str]],
    ) -> bool:
        """Create a new model"""
        pass

    @abstractmethod
    def update_model_templates(
        self,
        model_name: str,
        css: str,
        templates: list[dict[str, str]],
        card_name: str = "AnkicCard",
    ) -> bool:
        """Update existing model templates and styling"""
        pass

    @abstractmethod
    def ensure_model_fields(self, model_name: str, required_fields: list[str]) -> None:
        """Ensure all required fields exist on the model"""
        pass

    @abstractmethod
    def store_word_audio_files(
        self, word: str, audio_dir: str = "audio_files"
    ) -> AudioFiles:
        """Upload US/UK audio files to Anki media collection"""
        pass


class CacheManagerInterface(ABC):
    """Interface for cache management operations"""

    @abstractmethod
    def get_cached_word_info(self, word: str) -> WordInfo | None:
        """Get cached word information"""
        pass

    @abstractmethod
    def cache_word_info(self, word: str, word_info: WordInfo) -> None:
        """Cache word information"""
        pass

    @abstractmethod
    def check_audio_cache(self, word: str) -> dict[str, Any]:
        """Check if audio files exist for a word"""
        pass

    @abstractmethod
    def cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache"""
        pass


class TextProcessorInterface(ABC):
    """Interface for text processing operations"""

    @abstractmethod
    def clean_word(self, word: str) -> str | None:
        """Clean and validate word input"""
        pass

    @abstractmethod
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        pass

    @abstractmethod
    def extract_phonetic(self, phonetic_str: str) -> str:
        """Extract clean phonetic notation"""
        pass

    @abstractmethod
    def abbreviate_part_of_speech(self, part: str) -> str:
        """Convert part of speech to standard abbreviations"""
        pass

    @abstractmethod
    def bold_word_in_text(self, text: str, word: str) -> str:
        """Bold occurrences of word in text (case-insensitive, word boundary)"""
        pass


class ContentEnricherInterface(ABC):
    """Interface for adding extra content to card fields"""

    @abstractmethod
    def enrich(self, word: str, info: WordInfo | None) -> dict[str, str]:
        """Return a mapping of additional Anki fields for this word"""
        pass
