"""Comprehensive tests for cache management functionality."""

import json
import time
from pathlib import Path

from anki_connector.models.cache_models import CacheConfig
from anki_connector.models.word_info import (
    Phonetics,
    WordDefinition,
    WordForms,
    WordInfo,
)
from anki_connector.utils.cache_engine import CacheEngine
from anki_connector.utils.cache_manager import CacheManager


class TestCacheManager:
    """Test class for cache management functionality."""

    def sample_word_info(self) -> WordInfo:
        """Create sample WordInfo for testing."""
        return WordInfo(
            word="example",
            phonetics=Phonetics(us="/ɪgˈzæmpəl/", uk="/ɪgˈzɑːmpəl/"),
            definitions=[
                WordDefinition(
                    part_of_speech="noun",
                    definition="a representative form or pattern",
                    examples=["an example sentence"],
                    synonyms=["instance"],
                    antonyms=[],
                ),
                WordDefinition(
                    part_of_speech="verb",
                    definition="to serve as an example",
                    examples=[],
                    synonyms=[],
                    antonyms=[],
                ),
            ],
            word_forms=WordForms(forms=["examples", "exemplified"]),
            short_explanation="a simple explanation",
            long_explanation="a longer explanation here",
        )

    def test_cache_set_get_roundtrip(self, tmp_path):
        """Test basic cache set/get operations."""
        # Use the cache manager directly for set/get roundtrip
        cfg = CacheConfig(ttl_days=1, max_size_mb=10)
        cm = CacheEngine(cfg, tmp_path)
        wi = self.sample_word_info()
        key = cm.get_cache_key(wi.word)
        cm.set(key, wi.model_dump())
        out = cm.get(key)
        assert out and out["word"] == "example"

    def test_check_audio_cache(self, tmp_path):
        """Test audio cache checking functionality."""
        # create dummy us/uk files
        (tmp_path / "example_us.mp3").write_bytes(b"\x00")
        (tmp_path / "example_uk_youdao.mp3").write_bytes(b"\x00")
        cm = CacheManager(audio_dir=str(tmp_path))
        status = cm.check_audio_cache("example")
        assert status["us_exists"] is True
        assert status["uk_exists"] is True

    def test_cache_engine_key_generation(self, tmp_path):
        """Test cache key generation."""
        cfg = CacheConfig(ttl_days=1, max_size_mb=10)
        cm = CacheEngine(cfg, tmp_path)

        # Test basic key generation
        key1 = cm.get_cache_key("test")
        key2 = cm.get_cache_key("test")
        assert key1 == key2  # Same word should generate same key

        key3 = cm.get_cache_key("different")
        assert key1 != key3  # Different words should generate different keys

    def test_cache_with_different_data_types(self, tmp_path):
        """Test caching different types of data."""
        cfg = CacheConfig(ttl_days=1, max_size_mb=10)
        cm = CacheEngine(cfg, tmp_path)

        # Test caching different data structures
        test_cases = [
            ("simple_string", "hello world"),
            ("simple_dict", {"key": "value", "number": 42}),
            ("complex_dict", {"nested": {"data": [1, 2, 3]}, "list": ["a", "b"]}),
            ("word_info", self.sample_word_info().model_dump()),
        ]

        for test_name, test_data in test_cases:
            key = cm.get_cache_key(test_name)
            cm.set(key, test_data)
            retrieved = cm.get(key)
            assert retrieved == test_data, f"Failed for {test_name}"

    def test_cache_manager_integration(self, tmp_path):
        """Test CacheManager integration functionality."""
        cm = CacheManager(audio_dir=str(tmp_path))

        # Test cache stats
        stats = cm.get_cache_stats()
        assert "total" in stats
        assert "valid" in stats
        assert "expired" in stats

    def test_audio_file_patterns(self, tmp_path):
        """Test audio file pattern matching."""
        cm = CacheManager(audio_dir=str(tmp_path))

        # Create various audio file patterns matching AudioConstants patterns
        test_files = [
            "word_us.mp3",
            "word_uk_youdao.mp3",
            "another_us.mp3",
            "another_uk_youdao.mp3",
            "different_us.mp3",
            "unrelated.mp3",  # Should not match
        ]

        for filename in test_files:
            (tmp_path / filename).write_bytes(b"test audio")

        # Test specific word audio cache
        status = cm.check_audio_cache("word")
        assert status["us_exists"] is True
        assert status["uk_exists"] is True

        status = cm.check_audio_cache("another")
        assert status["us_exists"] is True
        assert status["uk_exists"] is True

        status = cm.check_audio_cache("nonexistent")
        assert status["us_exists"] is False
        assert status["uk_exists"] is False
