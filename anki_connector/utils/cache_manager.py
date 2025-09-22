"""Unified cache management using the layered cache engine.

All caching is handled by CacheEngine (memory + disk with JSON index).
"""

import os
from typing import Any

from ..config.settings import settings
from ..core.constants import get_audio_patterns
from ..core.interfaces import CacheManagerInterface
from ..logging_config import get_logger
from ..models.cache_models import CacheConfig
from ..models.word_info import WordInfo
from .cache_engine import CacheEngine

logger = get_logger(__name__)


class CacheManager(CacheManagerInterface):
    """Cache manager facade."""

    def __init__(self, audio_dir: str = "audio_files", cache_expiry_days: int = 30):
        config = CacheConfig(
            ttl_days=cache_expiry_days, max_size_mb=settings.cache.max_size_mb
        )
        self._cache = CacheEngine(config, settings.cache.dir)
        self.audio_dir = audio_dir
        self.cache_expiry_days = cache_expiry_days

    def get_cached_word_info(self, word: str) -> WordInfo | None:
        """Get cached word information"""
        cached_dict = self._cache.get_cached_word_info(word)
        if cached_dict:
            return self._dict_to_word_info(cached_dict)
        return None

    def cache_word_info(self, word: str, word_info: WordInfo) -> None:
        """Cache word information"""
        word_dict = self._word_info_to_dict(word_info)
        self._cache.cache_word_info(word, word_dict)

    def check_audio_cache(self, word: str) -> dict[str, Any]:
        """Check if audio files exist for a word"""
        audio_status: dict[str, Any] = {
            "us_exists": False,
            "uk_exists": False,
            "us_file": None,
            "uk_file": None,
        }

        if not os.path.exists(self.audio_dir):
            return audio_status

        patterns = get_audio_patterns(word)

        # Check US audio
        for pattern in patterns["us_patterns"]:
            file_path = os.path.join(self.audio_dir, pattern)
            if os.path.exists(file_path):
                audio_status["us_exists"] = True
                audio_status["us_file"] = pattern
                break

        # Check UK audio
        for pattern in patterns["uk_patterns"]:
            file_path = os.path.join(self.audio_dir, pattern)
            if os.path.exists(file_path):
                audio_status["uk_exists"] = True
                audio_status["uk_file"] = pattern
                break

        return audio_status

    def cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache"""
        self._cache.cleanup_expired()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics"""
        stats = self._cache.get_stats()
        return {
            "total": stats.total_entries,
            "valid": stats.valid_entries,
            "expired": stats.expired_entries,
        }

    def _dict_to_word_info(self, data: dict[str, Any]) -> WordInfo:
        """Convert dictionary data to WordInfo object"""
        return WordInfo(**data)

    def _word_info_to_dict(self, word_info: WordInfo) -> dict[str, Any]:
        """Convert WordInfo object to dictionary for caching"""
        return word_info.model_dump()


# NoCacheManager removed; caching is always enabled in this application stage.
