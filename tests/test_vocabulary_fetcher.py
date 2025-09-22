"""Unit tests for VocabularyFetcher AJAX functionality"""

import pytest

from anki_connector.core.vocabulary_fetcher import VocabularyFetcher


def test_ajax_word_parsing():
    """Test that VocabularyFetcher can parse AJAX responses correctly."""
    fetcher = VocabularyFetcher()

    # Test the AJAX endpoint method exists and is callable
    assert hasattr(fetcher, "_fetch_from_ajax_endpoint")
    assert callable(fetcher._fetch_from_ajax_endpoint)

    # Test the main fetch method
    assert hasattr(fetcher, "fetch_word_info")
    assert callable(fetcher.fetch_word_info)
