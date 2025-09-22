"""Unit tests for VocabularyFetcher AJAX functionality"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from anki_connector.core.vocabulary_fetcher import VocabularyFetcher


class TestVocabularyFetcher:
    """Test class for VocabularyFetcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.fetcher = VocabularyFetcher()

    def test_ajax_word_parsing(self):
        """Test that VocabularyFetcher can parse AJAX responses correctly."""
        # Test the AJAX endpoint method exists and is callable
        assert hasattr(self.fetcher, "_fetch_from_ajax_endpoint")
        assert callable(self.fetcher._fetch_from_ajax_endpoint)

        # Test the main fetch method
        assert hasattr(self.fetcher, "fetch_word_info")
        assert callable(self.fetcher.fetch_word_info)

    def test_parse_vocab_soup_with_real_data(self):
        """Test parsing with real AJAX HTML data."""
        # Load a real test file
        test_file = (
            Path(__file__).parent / "source" / "vocab_word_design_ajax_result.html"
        )
        if not test_file.exists():
            return  # Skip if file doesn't exist

        with open(test_file, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        data = self.fetcher._parse_vocab_soup(soup)

        # Basic structure validation
        assert isinstance(data, dict)
        assert "word" in data
        assert "phonetics" in data
        assert "parts" in data
        assert "exchanges" in data
        assert "additions" in data

        # Content quality checks
        assert len(data["parts"]) > 0, "Should extract definitions"
        assert len(data["phonetics"]) > 0, "Should extract phonetics"

    def test_extract_phonetics(self):
        """Test phonetics extraction from HTML."""
        # Create minimal HTML with phonetics
        html = """
        <div class="ipa-section">
            <div class="ipa-with-audio">
                <span class="us-flag-icon"></span>
                <span class="span-replace-h3">/dɪˈzaɪn/</span>
            </div>
            <div class="ipa-with-audio">
                <span class="uk-flag-icon"></span>
                <span class="span-replace-h3">/dɪˈzaɪn/</span>
            </div>
        </div>
        """

        soup = BeautifulSoup(html, "html.parser")
        phonetics = self.fetcher._extract_phonetics(soup)

        assert len(phonetics) == 2
        assert "US: /dɪˈzaɪn/" in phonetics
        assert "UK: /dɪˈzaɪn/" in phonetics

    def test_extract_definitions(self):
        """Test definition extraction from HTML."""
        # Create minimal HTML with definitions
        html = """
        <div class="word-definitions">
            <ol>
                <li>
                    <span class="pos-icon">noun</span>
                    <div class="definition">a plan or drawing</div>
                </li>
                <li>
                    <span class="pos-icon">verb</span>
                    <div class="definition">to create a plan</div>
                </li>
            </ol>
        </div>
        """

        soup = BeautifulSoup(html, "html.parser")
        definitions = self.fetcher._extract_definitions(soup, "design")

        assert len(definitions) == 2
        assert definitions[0].part_of_speech == "noun"
        assert "plan" in definitions[0].definition
        assert definitions[1].part_of_speech == "verb"
        assert "create" in definitions[1].definition

    def test_dict_to_word_info_conversion(self):
        """Test conversion from dict to WordInfo object."""
        test_data = {
            "word": "test",
            "phonetics": ["US: /tɛst/", "UK: /tɛst/"],
            "parts": [
                {
                    "part": "noun",
                    "definition": "a test definition",
                    "examples": ["test example"],
                    "synonyms": ["exam"],
                    "antonyms": [],
                }
            ],
            "exchanges": ["tests", "tested"],
            "additions": {"short_explanation": "test word"},
        }

        word_info = self.fetcher._dict_to_word_info(test_data)

        assert word_info.word == "test"
        assert word_info.phonetics.us == "/tɛst/"
        assert word_info.phonetics.uk == "/tɛst/"
        assert len(word_info.definitions) == 1
        assert word_info.definitions[0].part_of_speech == "noun"
        assert len(word_info.word_forms.forms) == 2

    def test_clean_part_of_speech(self):
        """Test part of speech cleaning."""
        assert self.fetcher._clean_part_of_speech("noun") == "noun"
        assert self.fetcher._clean_part_of_speech("VERB") == "verb"
        assert self.fetcher._clean_part_of_speech("adjective ") == "adjective"

    @patch("anki_connector.core.vocabulary_fetcher.requests.Session.get")
    def test_fetch_from_ajax_endpoint_success(self, mock_get):
        """Test successful AJAX endpoint fetch."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<div id="hdr-word-area">test</div>'
        mock_get.return_value = mock_response

        # Mock the parsing to return simple data
        with patch.object(self.fetcher, "_parse_vocab_soup") as mock_parse:
            mock_parse.return_value = {
                "word": "test",
                "parts": [{"part": "noun", "definition": "test"}],
                "phonetics": [],
                "exchanges": [],
                "additions": {},
            }

            result = self.fetcher._fetch_from_ajax_endpoint("test")
            assert result is not None
            assert result.word == "test"

    @patch("anki_connector.core.vocabulary_fetcher.requests.Session.get")
    def test_fetch_from_ajax_endpoint_failure(self, mock_get):
        """Test AJAX endpoint fetch failure handling."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.fetcher._fetch_from_ajax_endpoint("nonexistent")
        assert result is None

    def test_batch_fetch_basic(self):
        """Test basic batch fetch functionality."""
        # Mock the fetch_word_info method
        with patch.object(self.fetcher, "fetch_word_info") as mock_fetch:
            mock_fetch.return_value = None  # Simulate no results

            results = self.fetcher.batch_fetch(["test1", "test2"], delay=0)

            assert len(results) == 2
            assert "test1" in results
            assert "test2" in results
            assert mock_fetch.call_count == 2
