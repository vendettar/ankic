"""CLI tests covering all usage scenarios"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anki_connector.cli import create_parser, main, merge_results, process_words_main
from anki_connector.core.vocabulary_processor import (
    BatchProcessingResult,
    ProcessingResult,
)


class TestCLIArgumentParsing:
    """Test CLI argument parsing for different scenarios"""

    def test_single_word_args(self):
        """Test parsing single word arguments"""
        parser = create_parser()
        args = parser.parse_args(["hello"])

        assert args.words == ["hello"]
        assert args.deck == "Ankic"  # default deck
        assert args.no_audio is False

    def test_multiple_word_args(self):
        """Test parsing multiple word arguments"""
        parser = create_parser()
        args = parser.parse_args(["hello", "world", "test"])

        assert args.words == ["hello", "world", "test"]
        assert len(args.words) == 3

    def test_file_args(self):
        """Test parsing file arguments"""
        parser = create_parser()
        args = parser.parse_args(["words.txt"])

        assert args.words == ["words.txt"]
        assert args.words[0].endswith(".txt")

    def test_mixed_args(self):
        """Test parsing mixed word and file arguments"""
        parser = create_parser()
        args = parser.parse_args(["hello", "words.txt", "world", "more_words.txt"])

        assert "hello" in args.words
        assert "words.txt" in args.words
        assert "world" in args.words
        assert "more_words.txt" in args.words
        assert len(args.words) == 4

    def test_custom_deck_option(self):
        """Test custom deck name option"""
        parser = create_parser()
        args = parser.parse_args(["--deck", "MyCustomDeck", "hello", "world"])

        assert args.deck == "MyCustomDeck"
        assert args.words == ["hello", "world"]

    def test_no_audio_option(self):
        """Test no audio option"""
        parser = create_parser()
        args = parser.parse_args(["--no-audio", "hello"])

        assert args.no_audio is True
        assert args.words == ["hello"]

    def test_force_update_option(self):
        """Test force update option"""
        parser = create_parser()
        args = parser.parse_args(["--force-update", "hello"])

        assert args.force_update is True

    def test_interval_option(self):
        """Test custom interval option"""
        parser = create_parser()
        args = parser.parse_args(["--interval", "2.5", "hello"])

        assert args.interval == 2.5

    def test_cache_options(self):
        """Test cache-related options"""
        parser = create_parser()

        # Test clear cache (specific words)
        args1 = parser.parse_args(["--clear-cache", "hello", "world"])
        assert args1.clear_cache == ["hello", "world"]

        # Test clear all cache (no words)
        args1b = parser.parse_args(["--clear-cache"])
        assert args1b.clear_cache == []

        # Test cache stats
        args2 = parser.parse_args(["--cache-stats"])
        assert args2.cache_stats is True

    def test_verbose_and_debug_options(self):
        """Test logging options"""
        parser = create_parser()

        # Test verbose
        args1 = parser.parse_args(["--verbose", "hello"])
        assert args1.verbose is True

        # Test debug
        args2 = parser.parse_args(["--debug", "hello"])
        assert args2.debug is True

    def test_template_option(self):
        """Test template selection option"""
        parser = create_parser()
        args = parser.parse_args(["--template", "vapor", "hello"])

        assert args.template == "vapor"

    def test_stats_option(self):
        """Test stats option"""
        parser = create_parser()
        args = parser.parse_args(["--stats", "hello"])

        assert args.stats is True


class TestCLIWordFileProcessing:
    """Test CLI processing of different input types"""

    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_process_single_word_cli(self, mock_factory):
        """Test CLI processing of single word"""
        # Setup mock processor
        mock_processor = MagicMock()
        mock_result = BatchProcessingResult(1, 1, 0, 0, [], [])
        mock_processor.process_word_list.return_value = mock_result
        mock_processor.get_statistics.return_value = {
            "cache_hits": 0,
            "cache_misses": 1,
        }
        mock_factory.return_value = mock_processor

        # Create mock args
        args = MagicMock()
        args.words = ["hello"]
        args.deck = "TestDeck"
        args.template = None
        args.no_audio = False
        args.interval = 1.0
        args.force_update = False
        args.stats = False

        # Process words
        process_words_main(args)

        # Verify processor was called correctly
        mock_factory.assert_called_once_with(deck_name="TestDeck", template=None)
        mock_processor.process_word_list.assert_called_once_with(
            ["hello"], include_audio=True, delay=1.0, force_update=False
        )

    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_process_multiple_words_cli(self, mock_factory):
        """Test CLI processing of multiple words"""
        # Setup mock processor
        mock_processor = MagicMock()
        mock_result = BatchProcessingResult(3, 3, 0, 0, [], [])
        mock_processor.process_word_list.return_value = mock_result
        mock_factory.return_value = mock_processor

        # Create mock args
        args = MagicMock()
        args.words = ["hello", "world", "test"]
        args.deck = "TestDeck"
        args.template = None
        args.no_audio = True
        args.interval = 0.5
        args.force_update = True
        args.stats = False

        # Process words
        process_words_main(args)

        # Verify processor was called correctly
        mock_processor.process_word_list.assert_called_once_with(
            ["hello", "world", "test"],
            include_audio=False,  # no_audio = True
            delay=0.5,
            force_update=True,
        )

    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_process_file_cli(self, mock_factory):
        """Test CLI processing of file"""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\\nworld\\ntest\\n")
            temp_file = f.name

        try:
            # Setup mock processor
            mock_processor = MagicMock()
            mock_result = BatchProcessingResult(3, 3, 0, 0, [], [])
            mock_processor.process_file.return_value = mock_result
            mock_factory.return_value = mock_processor

            # Create mock args
            args = MagicMock()
            args.words = [temp_file]
            args.deck = "TestDeck"
            args.template = "vapor"
            args.no_audio = False
            args.interval = 1.0
            args.force_update = False
            args.stats = True

            # Process words
            process_words_main(args)

            # Verify processor was called correctly
            mock_factory.assert_called_once_with(deck_name="TestDeck", template="vapor")
            mock_processor.process_file.assert_called_once_with(
                temp_file, include_audio=True, delay=1.0, force_update=False
            )
            mock_processor.get_statistics.assert_called_once()

        finally:
            # Cleanup
            Path(temp_file).unlink()

    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_process_mixed_input_cli(self, mock_factory):
        """Test CLI processing of mixed words and files"""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file_word1\\nfile_word2\\n")
            temp_file = f.name

        try:
            # Setup mock processor
            mock_processor = MagicMock()
            mock_result1 = BatchProcessingResult(2, 2, 0, 0, [], [])  # for words
            mock_result2 = BatchProcessingResult(2, 2, 0, 0, [], [])  # for file
            mock_processor.process_word_list.return_value = mock_result1
            mock_processor.process_file.return_value = mock_result2
            mock_factory.return_value = mock_processor

            # Create mock args with mixed input
            args = MagicMock()
            args.words = ["hello", "world", temp_file]
            args.deck = "TestDeck"
            args.template = None
            args.no_audio = False
            args.interval = 1.0
            args.force_update = False
            args.stats = False

            # Process words
            process_words_main(args)

            # Verify both word list and file processing were called
            mock_processor.process_word_list.assert_called_once_with(
                ["hello", "world"],  # Only non-.txt arguments
                include_audio=True,
                delay=1.0,
                force_update=False,
            )
            mock_processor.process_file.assert_called_once_with(
                temp_file, include_audio=True, delay=1.0, force_update=False
            )

        finally:
            # Cleanup
            Path(temp_file).unlink()

    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_process_nonexistent_file_cli(self, mock_factory):
        """Test CLI handling of nonexistent files"""
        # Setup mock processor with proper BatchProcessingResult
        mock_processor = MagicMock()
        mock_result = BatchProcessingResult(1, 1, 0, 0, [], [])
        mock_processor.process_word_list.return_value = mock_result
        mock_factory.return_value = mock_processor

        # Create mock args with nonexistent file
        args = MagicMock()
        args.words = ["hello", "nonexistent_file.txt"]
        args.deck = "TestDeck"
        args.template = None
        args.no_audio = False
        args.interval = 1.0
        args.force_update = False
        args.stats = False

        # Process words (should handle gracefully)
        process_words_main(args)

        # Verify word processing was still called
        mock_processor.process_word_list.assert_called_once_with(
            ["hello"], include_audio=True, delay=1.0, force_update=False
        )
        # File processing should not be called for nonexistent file
        mock_processor.process_file.assert_not_called()


class TestCLIBatchResultMerging:
    """Test merging of batch results from different sources"""

    def test_merge_empty_results(self):
        """Test merging empty results list"""
        result = merge_results([])

        assert result.total_processed == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert len(result.results) == 0
        assert len(result.errors) == 0

    def test_merge_single_result(self):
        """Test merging single result"""
        word_result = ProcessingResult(
            word="hello", success=True, note_id=12345, error=None, skipped_reason=None
        )
        batch_result = BatchProcessingResult(1, 1, 0, 0, [word_result], [])

        merged = merge_results([batch_result])

        assert merged.total_processed == 1
        assert merged.successful == 1
        assert merged.failed == 0
        assert merged.skipped == 0
        assert len(merged.results) == 1
        assert merged.results[0].word == "hello"

    def test_merge_multiple_results(self):
        """Test merging multiple batch results"""
        # Create first batch result (words)
        word_result1 = ProcessingResult("hello", True, 12345, None, None)
        word_result2 = ProcessingResult("world", True, 12346, None, None)
        batch1 = BatchProcessingResult(2, 2, 0, 0, [word_result1, word_result2], [])

        # Create second batch result (file)
        word_result3 = ProcessingResult("test", True, 12347, None, None)
        word_result4 = ProcessingResult("invalid", False, None, "Invalid word", None)
        batch2 = BatchProcessingResult(
            2, 1, 1, 0, [word_result3, word_result4], ["Error processing invalid"]
        )

        # Merge results
        merged = merge_results([batch1, batch2])

        # Verify merged totals
        assert merged.total_processed == 4
        assert merged.successful == 3
        assert merged.failed == 1
        assert merged.skipped == 0
        assert len(merged.results) == 4
        assert len(merged.errors) == 1

        # Verify individual results were preserved
        result_words = [r.word for r in merged.results]
        assert "hello" in result_words
        assert "world" in result_words
        assert "test" in result_words
        assert "invalid" in result_words


class TestCLIEndToEnd:
    """End-to-end CLI tests"""

    @patch("anki_connector.cli.setup_logging")
    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_cli_help_display(self, mock_factory, mock_logging):
        """Test CLI help display"""
        parser = create_parser()
        help_text = parser.format_help()

        # Verify key help sections are present
        assert "ankic word1 word2 word3" in help_text
        assert "ankic my_words.txt" in help_text
        assert "--deck MyDeck" in help_text
        assert "--no-audio" in help_text
        assert "audio options" in help_text
        assert "processing options" in help_text
        assert "cache options" in help_text

    @patch("anki_connector.cli.show_cache_stats")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_cache_stats_only(self, mock_logging, mock_cache_stats):
        """Test CLI cache stats command"""
        # Mock sys.argv for cache stats only
        with patch("sys.argv", ["ankic", "--cache-stats"]):
            try:
                main()
            except SystemExit:
                pass  # Expected for successful completion

            mock_cache_stats.assert_called_once()

    @patch("anki_connector.cli.clear_vocabulary_cache")
    @patch("anki_connector.cli.setup_logging")
    def test_cli_clear_cache_only(self, mock_logging, mock_clear_cache):
        """Test CLI clear cache command"""
        # Mock sys.argv for clear cache only
        with patch("sys.argv", ["ankic", "--clear-cache"]):
            try:
                main()
            except SystemExit:
                pass  # Expected for successful completion

            mock_clear_cache.assert_called_once()


class TestCLIErrorHandling:
    """Test CLI error handling scenarios"""

    @patch("anki_connector.cli.setup_logging")
    def test_cli_no_arguments_shows_help(self, mock_logging):
        """Test CLI shows help when no arguments provided"""
        with patch("sys.argv", ["ankic"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with code 0 (help display)
            assert exc_info.value.code == 0

    @patch("anki_connector.cli.setup_logging")
    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_cli_handles_keyboard_interrupt(self, mock_factory, mock_logging):
        """Test CLI handles keyboard interrupt gracefully"""
        mock_processor = MagicMock()
        mock_processor.process_word_list.side_effect = KeyboardInterrupt()
        mock_factory.return_value = mock_processor

        with patch("sys.argv", ["ankic", "hello"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with code 130 (SIGINT)
            assert exc_info.value.code == 130

    @patch("anki_connector.cli.setup_logging")
    @patch("anki_connector.cli.create_vocabulary_processor")
    def test_cli_handles_processing_errors(self, mock_factory, mock_logging):
        """Test CLI handles processing errors"""
        mock_processor = MagicMock()
        mock_processor.process_word_list.side_effect = Exception("Processing failed")
        mock_factory.return_value = mock_processor

        with patch("sys.argv", ["ankic", "hello"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error code 1
            assert exc_info.value.code == 1
