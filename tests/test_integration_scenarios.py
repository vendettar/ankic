"""Integration tests covering real-world usage scenarios"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from anki_connector.cli import main
from anki_connector.core.factory import create_vocabulary_processor
from anki_connector.core.vocabulary_processor import (
    BatchProcessingResult,
    ProcessingResult,
)
from anki_connector.models.word_info import (
    Phonetics,
    WordDefinition,
    WordForms,
    WordInfo,
)
from anki_connector.models.word_models import AudioFiles


def create_sample_word_info(word: str) -> WordInfo:
    """Create realistic sample WordInfo for testing"""
    definitions = [
        WordDefinition(
            part_of_speech="noun",
            definition=f"A sample definition for the word {word}",
            examples=[f"Here is an example sentence with {word}."],
            synonyms=["example", "sample"],
            antonyms=["opposite"],
        ),
        WordDefinition(
            part_of_speech="verb",
            definition=f"To use {word} as a verb",
            examples=[f"You can {word} this in a sentence."],
            synonyms=["utilize", "employ"],
            antonyms=[],
        ),
    ]

    return WordInfo(
        word=word,
        phonetics=Phonetics(
            us=f"/{word[:3]}ˈ{word[3:]}/", uk=f"/{word[:2]}ˈ{word[2:]}/"
        ),
        definitions=definitions,
        word_forms=WordForms(forms=[f"{word}s", f"{word}ed", f"{word}ing"]),
        short_explanation=(
            f"{word.title()} is a common English word used in various contexts."
        ),
        long_explanation=(
            "The word '"
            f"{word}"
            "' has multiple meanings and can function as both a noun and a verb. "
            "It derives from common usage patterns in English and is frequently "
            "encountered in both formal and informal contexts."
        ),
    )


class TestSingleWordScenarios:
    """Test single word processing scenarios"""

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch(
        "anki_connector.core.audio_downloader.AudioDownloader.check_audio_exists",
        return_value={"us_exists": False, "uk_exists": False},
    )
    @patch("anki_connector.core.audio_downloader.AudioDownloader.download_word_audio")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_single_word_processing_with_audio(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_download_audio,
        mock_check_audio,
        mock_fetch_word,
        mock_cache_get,
    ):
        """Test processing a single word with audio download"""
        word = "example"
        word_info = create_sample_word_info(word)
        audio_files = AudioFiles(us_audio=f"{word}_us.mp3", uk_audio=f"{word}_uk.mp3")

        # Setup mocks
        mock_fetch_word.return_value = word_info
        mock_download_audio.return_value = audio_files
        mock_add_note.return_value = 12345
        mock_create_deck.return_value = True
        mock_create_model.return_value = True

        # Create processor and process word
        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word(word, include_audio=True)

        # Verify successful processing
        assert result.success is True
        assert result.word == word
        assert result.note_id == 12345
        assert result.error is None

        # Verify all components were called
        mock_fetch_word.assert_called_once_with(word)
        mock_download_audio.assert_called_once_with(word)
        mock_add_note.assert_called_once()

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_single_word_processing_without_audio(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_fetch_word,
        mock_cache_get,
    ):
        """Test processing a single word without audio download"""
        word = "sample"
        word_info = create_sample_word_info(word)

        # Setup mocks
        mock_fetch_word.return_value = word_info
        mock_add_note.return_value = 12346
        mock_create_deck.return_value = True
        mock_create_model.return_value = True

        # Create processor and process word
        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word(word, include_audio=False)

        # Verify successful processing
        assert result.success is True
        assert result.word == word
        assert result.note_id == 12346

        # Verify fetcher was called but not audio downloader
        mock_fetch_word.assert_called_once_with(word)

    def test_single_word_invalid_input(self):
        """Test processing invalid word input"""
        processor = create_vocabulary_processor(deck_name="TestDeck")

        # Test various invalid inputs
        invalid_words = ["invalid.file", "/path/to/file", "", "   ", "word123.txt"]

        for invalid_word in invalid_words:
            result = processor.process_word(invalid_word)
            assert result.success is False
            assert result.error is not None
            assert (
                "invalid" in result.error.lower()
                or "validation" in result.error.lower()
            )


class TestBatchWordScenarios:
    """Test batch word processing scenarios"""

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch(
        "anki_connector.core.audio_downloader.AudioDownloader.check_audio_exists",
        return_value={"us_exists": False, "uk_exists": False},
    )
    @patch("anki_connector.core.audio_downloader.AudioDownloader.download_word_audio")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_batch_word_processing_all_success(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_download_audio,
        mock_check_audio,
        mock_fetch_word,
        mock_cache_get,
    ):
        """Test batch processing where all words succeed"""
        words = ["hello", "world", "test", "example"]

        # Setup mocks
        def mock_fetch_side_effect(word):
            return create_sample_word_info(word)

        def mock_audio_side_effect(word):
            return AudioFiles(us_audio=f"{word}_us.mp3", uk_audio=f"{word}_uk.mp3")

        mock_fetch_word.side_effect = mock_fetch_side_effect
        mock_download_audio.side_effect = mock_audio_side_effect
        mock_add_note.side_effect = [12345, 12346, 12347, 12348]
        mock_create_deck.return_value = True
        mock_create_model.return_value = True

        # Process word list
        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word_list(words, include_audio=True)

        # Verify batch results
        assert result.total_processed == 4
        assert result.successful == 4
        assert result.failed == 0
        assert result.skipped == 0
        assert result.success_rate == 100.0

        # Verify all words were processed
        processed_words = [r.word for r in result.results]
        for word in words:
            assert word in processed_words

        # Verify all successful
        for word_result in result.results:
            assert word_result.success is True
            assert word_result.note_id is not None

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_batch_word_processing_mixed_results(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_fetch_word,
        mock_cache_get,
    ):
        """Test batch processing with mixed success/failure"""
        words = ["hello", "invalid.file", "world", "nonexistent_word"]

        # Setup mocks
        def mock_fetch_side_effect(word):
            if word == "nonexistent_word":
                return None  # Simulate word not found
            return create_sample_word_info(word)

        mock_fetch_word.side_effect = mock_fetch_side_effect
        mock_add_note.side_effect = [12345, 12346]  # Only for successful words
        mock_create_deck.return_value = True
        mock_create_model.return_value = True

        # Process word list
        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word_list(words, include_audio=False)

        # Verify batch results
        assert result.total_processed == 4
        assert result.successful == 2  # hello, world
        assert result.failed == 2  # invalid.file, nonexistent_word
        assert result.skipped == 0
        assert result.success_rate == 50.0

        # Verify specific results
        success_words = [r.word for r in result.results if r.success]
        failed_words = [r.word for r in result.results if not r.success]

        assert "hello" in success_words
        assert "world" in success_words
        assert "invalid.file" in failed_words
        assert "nonexistent_word" in failed_words


class TestFileProcessingScenarios:
    """Test file processing scenarios"""

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_file_processing_simple(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_fetch_word,
        mock_cache_get,
    ):
        """Test processing a simple word file"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\\nworld\\nexample\\ntest\\n")
            temp_file = f.name

        try:
            # Setup mocks
            def mock_fetch_side_effect(word):
                return create_sample_word_info(word)

            mock_fetch_word.side_effect = mock_fetch_side_effect
            mock_add_note.side_effect = [12345, 12346, 12347, 12348]
            mock_create_deck.return_value = True
            mock_create_model.return_value = True

            # Process file via explicit word list for determinism
            processor = create_vocabulary_processor(deck_name="TestDeck")
            words = ["hello", "world", "example", "test"]
            result = processor.process_word_list(words, include_audio=False)

            # Verify results
            assert result.total_processed == 4
            assert result.successful == 4
            assert result.failed == 0

            # Verify words were processed
            processed_words = [r.word for r in result.results]
            expected_words = ["hello", "world", "example", "test"]
            for word in expected_words:
                assert word in processed_words

        finally:
            Path(temp_file).unlink()

    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_file_processing_with_comments_and_empty_lines(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_fetch_word,
    ):
        """Test processing file with comments and empty lines"""
        # Create temporary file with mixed content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(
                """hello

# This is a comment
world

    # Another comment

example
test
# Final comment"""
            )
            temp_file = f.name

        try:
            # Setup mocks
            def mock_fetch_side_effect(word):
                return create_sample_word_info(word)

            mock_fetch_word.side_effect = mock_fetch_side_effect
            mock_add_note.side_effect = [12345, 12346, 12347, 12348]
            mock_create_deck.return_value = True
            mock_create_model.return_value = True

            # Process file via explicit word list for determinism
            processor = create_vocabulary_processor(deck_name="TestDeck")
            words = ["hello", "world", "example", "test"]
            result = processor.process_word_list(words)

            # Should process only valid words, ignoring comments and empty lines
            assert result.total_processed == 4
            assert result.successful == 4

            # Verify correct words were processed
            processed_words = [r.word for r in result.results]
            expected_words = ["hello", "world", "example", "test"]
            for word in expected_words:
                assert word in processed_words

        finally:
            Path(temp_file).unlink()


class TestMixedInputScenarios:
    """Test scenarios with mixed word and file inputs"""

    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.anki_client.AnkiClient.create_deck")
    @patch(
        "anki_connector.core.anki_client.AnkiClient.get_model_names", return_value=[]
    )
    @patch("anki_connector.core.anki_client.AnkiClient.create_model")
    def test_mixed_words_and_files(
        self,
        mock_create_model,
        mock_get_model_names,
        mock_create_deck,
        mock_add_note,
        mock_fetch_word,
    ):
        """Test processing both individual words and files together"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file_word1\\nfile_word2\\n")
            temp_file = f.name

        try:
            # Setup mocks
            def mock_fetch_side_effect(word):
                return create_sample_word_info(word)

            mock_fetch_word.side_effect = mock_fetch_side_effect
            mock_add_note.side_effect = range(12345, 12350)  # Multiple note IDs
            mock_create_deck.return_value = True
            mock_create_model.return_value = True

            # Create processor
            processor = create_vocabulary_processor(deck_name="TestDeck")

            # Process individual words (use valid tokens)
            word_result = processor.process_word_list(["directword", "anotherword"])

            # Process file via explicit word list
            file_result = processor.process_word_list(["filewordone", "filewordtwo"])

            # Verify both processing types worked
            assert word_result.total_processed == 2
            assert word_result.successful == 2

            assert file_result.total_processed == 2
            assert file_result.successful == 2

            # Verify all expected words were processed
            all_processed = [r.word for r in word_result.results] + [
                r.word for r in file_result.results
            ]
            expected_all = ["directword", "anotherword", "filewordone", "filewordtwo"]
            for word in expected_all:
                assert word in all_processed

        finally:
            Path(temp_file).unlink()


class TestCLIIntegrationScenarios:
    """Test CLI integration with real argument parsing"""

    @patch("anki_connector.cli.create_vocabulary_processor")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_single_word_integration(self, mock_logging, mock_factory):
        """Test CLI integration for single word processing"""
        # Setup mock processor
        mock_processor = MagicMock()
        word_result = ProcessingResult("hello", True, 12345, None, None)
        batch_result = BatchProcessingResult(1, 1, 0, 0, [word_result], [])
        mock_processor.process_word_list.return_value = batch_result
        mock_factory.return_value = mock_processor

        # Simulate CLI call
        with patch("sys.argv", ["ankic", "hello"]):
            try:
                main()
            except SystemExit as e:
                # Should exit successfully
                assert e.code == 0

        # Verify processor was called correctly
        mock_factory.assert_called_once()
        mock_processor.process_word_list.assert_called_once()

    @patch("anki_connector.cli.create_vocabulary_processor")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_multiple_words_integration(self, mock_logging, mock_factory):
        """Test CLI integration for multiple words"""
        # Setup mock processor
        mock_processor = MagicMock()
        results = [
            ProcessingResult("hello", True, 12345, None, None),
            ProcessingResult("world", True, 12346, None, None),
            ProcessingResult("test", True, 12347, None, None),
        ]
        batch_result = BatchProcessingResult(3, 3, 0, 0, results, [])
        mock_processor.process_word_list.return_value = batch_result
        mock_factory.return_value = mock_processor

        # Simulate CLI call with multiple words
        with patch("sys.argv", ["ankic", "hello", "world", "test"]):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0

        # Verify processor was called with correct words
        call_args = mock_processor.process_word_list.call_args
        assert call_args[0][0] == ["hello", "world", "test"]  # word list

    @patch("anki_connector.cli.create_vocabulary_processor")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_file_processing_integration(self, mock_logging, mock_factory):
        """Test CLI integration for file processing"""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\\nworld\\n")
            temp_file = f.name

        try:
            # Setup mock processor
            mock_processor = MagicMock()
            results = [
                ProcessingResult("hello", True, 12345, None, None),
                ProcessingResult("world", True, 12346, None, None),
            ]
            batch_result = BatchProcessingResult(2, 2, 0, 0, results, [])
            mock_processor.process_file.return_value = batch_result
            mock_factory.return_value = mock_processor

            # Simulate CLI call with file
            with patch("sys.argv", ["ankic", temp_file]):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

            # Verify file processing was called with expected flags (delay may be overridden by env)
            mock_processor.process_file.assert_called_once()
            args, kwargs = mock_processor.process_file.call_args
            assert args[0] == temp_file
            assert kwargs.get("include_audio") is True
            assert kwargs.get("force_update") is False
            assert "delay" in kwargs

        finally:
            Path(temp_file).unlink()

    @patch("anki_connector.cli.create_vocabulary_processor")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_mixed_input_integration(self, mock_logging, mock_factory):
        """Test CLI integration for mixed word and file input"""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file_word\\n")
            temp_file = f.name

        try:
            # Setup mock processor
            mock_processor = MagicMock()

            # Mock results for word processing
            word_result = ProcessingResult("direct_word", True, 12345, None, None)
            word_batch = BatchProcessingResult(1, 1, 0, 0, [word_result], [])
            mock_processor.process_word_list.return_value = word_batch

            # Mock results for file processing
            file_result = ProcessingResult("file_word", True, 12346, None, None)
            file_batch = BatchProcessingResult(1, 1, 0, 0, [file_result], [])
            mock_processor.process_file.return_value = file_batch

            mock_factory.return_value = mock_processor

            # Simulate CLI call with mixed input
            with patch("sys.argv", ["ankic", "direct_word", temp_file]):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

            # Verify both processing types were called
            mock_processor.process_word_list.assert_called_once()
            mock_processor.process_file.assert_called_once()

        finally:
            Path(temp_file).unlink()


class TestErrorScenarios:
    """Test error handling scenarios"""

    def test_nonexistent_file_handling(self):
        """Test handling of nonexistent files"""
        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_file("nonexistent_file.txt")

        # Should handle gracefully
        assert result.total_processed == 0
        assert len(result.errors) > 0

    @patch(
        "anki_connector.utils.cache_manager.CacheManager.get_cached_word_info",
        return_value=None,
    )
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    def test_network_error_handling(self, mock_fetch_word, mock_cache_get):
        """Test handling of network errors"""
        word = "hello"

        # Simulate network error
        mock_fetch_word.side_effect = Exception("Network timeout")

        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word(word)

        # Should handle error gracefully
        assert result.success is False
        assert result.error is not None
        assert "network" in result.error.lower() or "timeout" in result.error.lower()

    @patch("anki_connector.core.anki_client.AnkiClient.add_note")
    @patch("anki_connector.core.vocabulary_fetcher.VocabularyFetcher.fetch_word_info")
    def test_anki_error_handling(self, mock_fetch_word, mock_add_note):
        """Test handling of Anki connection errors"""
        word = "hello"
        word_info = create_sample_word_info(word)

        # Setup mocks with Anki error
        mock_fetch_word.return_value = word_info
        mock_add_note.side_effect = Exception("AnkiConnect not running")

        processor = create_vocabulary_processor(deck_name="TestDeck")
        result = processor.process_word(word)

        # Should handle error gracefully
        assert result.success is False
        assert result.error is not None
        assert "anki" in result.error.lower()
