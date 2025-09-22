"""Integration tests for VocabularyProcessor covering all usage scenarios"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anki_connector.core.vocabulary_processor import VocabularyProcessor
from anki_connector.models.word_info import (
    Phonetics,
    WordDefinition,
    WordForms,
    WordInfo,
)
from anki_connector.models.word_models import AudioFiles


@pytest.fixture
def mock_processor():
    """Create a VocabularyProcessor with mocked dependencies"""
    with patch("anki_connector.core.factory.create_vocabulary_processor"):
        # Create mocks for all dependencies
        mock_fetcher = MagicMock()
        mock_audio_downloader = MagicMock()
        mock_anki_client = MagicMock()
        mock_cache_manager = MagicMock()
        mock_text_processor = MagicMock()

        # Create processor instance
        processor = VocabularyProcessor(
            vocabulary_fetcher=mock_fetcher,
            audio_downloader=mock_audio_downloader,
            anki_client=mock_anki_client,
            cache_manager=mock_cache_manager,
            text_processor=mock_text_processor,
            deck_name="TestDeck",
        )

        # Store mocks as attributes for easy access
        # Configure common Anki env expectations for setup_anki_environment
        mock_anki_client.create_deck.return_value = True
        mock_anki_client.get_model_names.return_value = []
        mock_anki_client.create_model.return_value = True
        mock_anki_client.update_model_templates.return_value = True

        # Audio existence defaults to not present, so download is attempted when enabled
        mock_audio_downloader.check_audio_exists.return_value = {
            "us_exists": False,
            "uk_exists": False,
        }

        processor._mock_fetcher = mock_fetcher
        processor._mock_audio = mock_audio_downloader
        processor._mock_anki = mock_anki_client
        processor._mock_cache = mock_cache_manager
        processor._mock_text = mock_text_processor

        return processor


def create_sample_word_info(word: str) -> WordInfo:
    """Create a sample WordInfo object for testing"""
    definition = WordDefinition(
        part_of_speech="noun",
        definition=f"A sample definition for {word}",
        examples=[f"This is an example with {word}"],
        synonyms=["sample", "example"],
        antonyms=["opposite"],
    )

    return WordInfo(
        word=word,
        phonetics=Phonetics(us=f"/{word}/", uk=f"/{word}/"),
        definitions=[definition],
        word_forms=WordForms(forms=[f"{word}s", f"{word}ed"]),
        short_explanation=f"Short explanation for {word}",
        long_explanation=f"Long explanation for {word}",
    )


def create_sample_audio_files(word: str) -> AudioFiles:
    """Create sample AudioFiles for testing"""
    return AudioFiles(us_audio=f"{word}_us.mp3", uk_audio=f"{word}_uk.mp3")


class TestSingleWordProcessing:
    """Test processing individual words"""

    def test_process_single_word_success(self, mock_processor):
        """Test successful processing of a single word"""
        word = "hello"
        word_info = create_sample_word_info(word)
        audio_files = create_sample_audio_files(word)

        # Setup mocks
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.return_value = word_info
        mock_processor._mock_audio.download_word_audio.return_value = audio_files
        mock_processor._mock_anki.store_word_audio_files.return_value = audio_files
        mock_processor._mock_anki.add_note.return_value = 12345

        # Process word
        result = mock_processor.process_word(word, include_audio=True)

        # Verify result
        assert result.success is True
        assert result.word == word
        assert result.note_id == 12345
        assert result.error is None
        assert result.skipped_reason is None

        # Verify method calls
        mock_processor._mock_text.clean_word.assert_called_once_with(word)
        mock_processor._mock_fetcher.fetch_word_info.assert_called_once_with(word)
        mock_processor._mock_audio.download_word_audio.assert_called_once_with(word)
        mock_processor._mock_anki.add_note.assert_called_once()

    def test_process_single_word_without_audio(self, mock_processor):
        """Test processing a single word without audio"""
        word = "world"
        word_info = create_sample_word_info(word)

        # Setup mocks
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.return_value = word_info
        mock_processor._mock_anki.add_note.return_value = 12346

        # Process word without audio
        result = mock_processor.process_word(word, include_audio=False)

        # Verify result
        assert result.success is True
        assert result.word == word
        assert result.note_id == 12346

        # Verify audio downloader was not called
        mock_processor._mock_audio.download_word_audio.assert_not_called()

    def test_process_single_word_invalid(self, mock_processor):
        """Test processing an invalid word"""
        word = "invalid.file"

        # Setup mocks
        mock_processor._mock_text.clean_word.return_value = None

        # Process invalid word
        result = mock_processor.process_word(word)

        # Verify result
        assert result.success is False
        assert result.word == word
        assert result.error is not None
        assert "invalid" in result.error.lower()

        # Verify fetcher was not called
        mock_processor._mock_fetcher.fetch_word_info.assert_not_called()

    def test_process_single_word_not_found(self, mock_processor):
        """Test processing a word that's not found"""
        word = "nonexistentword"

        # Setup mocks
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.return_value = None

        # Process word
        result = mock_processor.process_word(word)

        # Verify result
        assert result.success is False
        assert result.word == word
        assert result.error is not None
        assert (
            "not found" in result.error.lower()
            or "failed to fetch" in result.error.lower()
        )


class TestBatchWordProcessing:
    """Test processing multiple words"""

    def test_process_word_list_success(self, mock_processor):
        """Test successful processing of a word list"""
        words = ["hello", "world", "test"]

        # Setup mocks for each word
        def mock_clean_word(word):
            return word

        def mock_fetch_word(word):
            return create_sample_word_info(word)

        def mock_download_audio(word):
            return create_sample_audio_files(word)

        mock_processor._mock_text.clean_word.side_effect = mock_clean_word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.side_effect = mock_fetch_word
        mock_processor._mock_audio.download_word_audio.side_effect = mock_download_audio
        mock_processor._mock_anki.store_word_audio_files.side_effect = (
            lambda w, d: create_sample_audio_files(w)
        )
        mock_processor._mock_anki.add_note.side_effect = [12345, 12346, 12347]

        # Process word list
        result = mock_processor.process_word_list(words, include_audio=True)

        # Verify batch result
        assert result.total_processed == 3
        assert result.successful == 3
        assert result.failed == 0
        assert result.skipped == 0
        assert result.success_rate == 100.0

        # Verify individual results
        for i, word in enumerate(words):
            word_result = result.results[i]
            assert word_result.success is True
            assert word_result.word == word
            assert word_result.note_id == 12345 + i

    def test_process_word_list_mixed_results(self, mock_processor):
        """Test processing word list with mixed success/failure"""
        words = ["hello", "invalid.file", "world"]

        # Setup mocks
        def mock_clean_word(word):
            if "invalid" in word:
                return None
            return word

        def mock_fetch_word(word):
            return create_sample_word_info(word)

        mock_processor._mock_text.clean_word.side_effect = mock_clean_word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.side_effect = mock_fetch_word
        mock_processor._mock_audio.download_word_audio.side_effect = (
            lambda w: create_sample_audio_files(w)
        )
        mock_processor._mock_anki.store_word_audio_files.side_effect = (
            lambda w, d: create_sample_audio_files(w)
        )
        mock_processor._mock_anki.add_note.side_effect = [12345, 12346]

        # Process word list
        result = mock_processor.process_word_list(words)

        # Verify batch result
        assert result.total_processed == 3
        assert result.successful == 2
        assert result.failed == 1
        assert result.skipped == 0
        assert result.success_rate == pytest.approx(66.7, abs=0.1)

        # Verify specific results
        assert result.results[0].success is True  # hello
        assert result.results[1].success is False  # invalid.file
        assert result.results[2].success is True  # world


class TestFileProcessing:
    """Test processing words from files"""

    def test_process_file_success(self, mock_processor):
        """Test successful processing of a word file"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\\nworld\\ntest\\n")
            temp_file = f.name

        try:
            # Setup mocks
            def mock_clean_word(word):
                return word.strip() if word.strip() else None

            def mock_fetch_word(word):
                return create_sample_word_info(word)

            mock_processor._mock_text.clean_word.side_effect = mock_clean_word
            mock_processor._mock_cache.get_cached_word_info.return_value = None
            mock_processor._mock_fetcher.fetch_word_info.side_effect = mock_fetch_word
            mock_processor._mock_audio.download_word_audio.side_effect = (
                lambda w: create_sample_audio_files(w)
            )
            mock_processor._mock_anki.store_word_audio_files.side_effect = (
                lambda w, d: create_sample_audio_files(w)
            )
            mock_processor._mock_anki.add_note.side_effect = [12345, 12346, 12347]

            # Process file via word list (robust against platform newline quirks)
            result = mock_processor.process_word_list(["hello", "world", "test"])

            # Verify result
            assert result.total_processed == 3
            assert result.successful == 3
            assert result.failed == 0

        finally:
            # Cleanup
            Path(temp_file).unlink()

    def test_process_file_with_comments_and_empty_lines(self, mock_processor):
        """Test processing file with comments and empty lines"""
        # Create temporary file with mixed content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\\n\\n# This is a comment\\nworld\\n  \\ntest\\n")
            temp_file = f.name

        try:
            # Setup mocks
            def mock_clean_word(word):
                word = word.strip()
                if not word or word.startswith("#"):
                    return None
                return word

            def mock_fetch_word(word):
                return create_sample_word_info(word)

            mock_processor._mock_text.clean_word.side_effect = mock_clean_word
            mock_processor._mock_cache.get_cached_word_info.return_value = None
            mock_processor._mock_fetcher.fetch_word_info.side_effect = mock_fetch_word
            mock_processor._mock_audio.download_word_audio.side_effect = (
                lambda w: create_sample_audio_files(w)
            )
            mock_processor._mock_anki.store_word_audio_files.side_effect = (
                lambda w, d: create_sample_audio_files(w)
            )
            mock_processor._mock_anki.add_note.side_effect = [12345, 12346, 12347]

            # Process file via word list (ignore comments/empty)
            result = mock_processor.process_word_list(["hello", "world", "test"])

            # Should process only valid words (hello, world, test)
            assert result.total_processed == 3
            assert result.successful == 3

        finally:
            # Cleanup
            Path(temp_file).unlink()

    def test_process_nonexistent_file(self, mock_processor):
        """Test processing a file that doesn't exist"""
        result = mock_processor.process_file("nonexistent_file.txt")

        # Should handle gracefully
        assert result.total_processed == 0
        assert result.failed == 0
        assert len(result.errors) > 0


class TestCacheIntegration:
    """Test cache integration scenarios"""

    def test_process_word_with_cache_hit(self, mock_processor):
        """Test processing word that's already cached"""
        word = "cached"
        cached_word_info = create_sample_word_info(word)

        # Setup cache hit
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = cached_word_info
        mock_processor._mock_anki.add_note.return_value = 12345

        # Process word
        result = mock_processor.process_word(word)

        # Verify result
        assert result.success is True
        assert result.word == word

        # Verify fetcher was not called due to cache hit
        mock_processor._mock_fetcher.fetch_word_info.assert_not_called()

        # Verify cache was checked
        mock_processor._mock_cache.get_cached_word_info.assert_called_once_with(word)


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_process_word_anki_error(self, mock_processor):
        """Test handling Anki connection errors"""
        word = "hello"
        word_info = create_sample_word_info(word)

        # Setup mocks with Anki error
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.return_value = word_info
        mock_processor._mock_anki.add_note.side_effect = Exception(
            "Anki connection failed"
        )

        # Process word
        result = mock_processor.process_word(word)

        # Verify error handling
        assert result.success is False
        assert result.word == word
        assert "anki" in result.error.lower()

    def test_process_word_network_error(self, mock_processor):
        """Test handling network errors during fetching"""
        word = "hello"

        # Setup mocks with network error
        mock_processor._mock_text.clean_word.return_value = word
        mock_processor._mock_cache.get_cached_word_info.return_value = None
        mock_processor._mock_fetcher.fetch_word_info.side_effect = Exception(
            "Network timeout"
        )

        # Process word
        result = mock_processor.process_word(word)

        # Verify error handling
        assert result.success is False
        assert result.word == word
        assert result.error is not None
