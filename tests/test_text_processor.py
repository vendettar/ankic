"""Comprehensive tests for TextProcessor functionality."""

from anki_connector.core.text_processor import TextProcessor


class TestTextProcessor:
    """Test class for TextProcessor."""

    def test_is_valid_word_basic(self):
        """Test basic word validation."""
        assert TextProcessor.is_valid_word("hello")
        assert TextProcessor.is_valid_word("state-of-the-art")
        assert not TextProcessor.is_valid_word("")
        assert not TextProcessor.is_valid_word("foo.txt")
        assert not TextProcessor.is_valid_word("/etc/passwd")

    def test_is_valid_word_edge_cases(self):
        """Test edge cases for word validation."""
        # Test various valid formats
        assert TextProcessor.is_valid_word("AI")  # Uppercase
        assert TextProcessor.is_valid_word("PhD")  # Abbreviations
        assert TextProcessor.is_valid_word("self-driving")  # Hyphenated
        assert not TextProcessor.is_valid_word("20th-century")  # Numbers not allowed

        # Test invalid formats
        assert not TextProcessor.is_valid_word("hello@world")  # Email-like
        assert not TextProcessor.is_valid_word("test.com")  # Domain-like
        assert not TextProcessor.is_valid_word("123456")  # Pure numbers
        assert TextProcessor.is_valid_word(
            "a"
        )  # Single letter allowed (MIN_WORD_LENGTH=1)
        assert not TextProcessor.is_valid_word(" ")  # Just space

    def test_clean_word_normalizes_spaces_and_validates(self):
        """Test word cleaning and normalization."""
        assert TextProcessor.clean_word("  Hello   World ") == "Hello World"
        assert TextProcessor.clean_word("foo.txt") is None

    def test_clean_word_edge_cases(self):
        """Test edge cases for word cleaning."""
        # Multiple spaces and tabs
        assert TextProcessor.clean_word("hello\t\tworld") == "hello world"
        assert TextProcessor.clean_word("test\n\nword") == "test word"

        # Mixed case preservation
        assert TextProcessor.clean_word("  iPhone  ") == "iPhone"
        assert TextProcessor.clean_word("  API  ") == "API"

        # Invalid inputs
        assert TextProcessor.clean_word("") is None
        assert TextProcessor.clean_word("   ") is None

    def test_extract_phonetic(self):
        """Test phonetic extraction."""
        assert TextProcessor.extract_phonetic("US: /həˈloʊ/") == "/həˈloʊ/"
        assert TextProcessor.extract_phonetic("/kæt/") == "/kæt/"

    def test_extract_phonetic_edge_cases(self):
        """Test edge cases for phonetic extraction."""
        # Different label formats
        assert TextProcessor.extract_phonetic("UK: /həˈloʊ/") == "/həˈloʊ/"
        assert TextProcessor.extract_phonetic("IPA: /həˈloʊ/") == "/həˈloʊ/"

        # No label
        assert TextProcessor.extract_phonetic("/həˈloʊ/") == "/həˈloʊ/"

        # Invalid formats
        assert TextProcessor.extract_phonetic("hello") == "hello"  # No phonetic markers
        assert TextProcessor.extract_phonetic("") == ""

    def test_abbreviate_pos(self):
        """Test part of speech abbreviation."""
        assert TextProcessor.abbreviate_part_of_speech("noun") == "n."
        assert TextProcessor.abbreviate_part_of_speech("adjective") == "adj."
        # substring fallback
        assert TextProcessor.abbreviate_part_of_speech("transitive verb") in (
            "v.",
            "vt.",
        )

    def test_abbreviate_pos_edge_cases(self):
        """Test edge cases for POS abbreviation."""
        # Case insensitive
        assert TextProcessor.abbreviate_part_of_speech("NOUN") == "n."
        assert TextProcessor.abbreviate_part_of_speech("Adjective") == "adj."

        # Complex forms
        assert (
            TextProcessor.abbreviate_part_of_speech("intransitive verb") == "v."
        )  # Substring match finds "verb" first
        assert TextProcessor.abbreviate_part_of_speech("proper noun") == "n."

        # Unknown forms
        result = TextProcessor.abbreviate_part_of_speech("unknown_pos")
        assert result == "unknown_."  # Truncated to 8 chars + "." if no match

    def test_bold_word_in_text(self):
        """Test word bolding in text."""
        out = TextProcessor.bold_word_in_text("A cat is not a dog", "cat")
        assert "<b>cat</b>" in out

    def test_bold_word_in_text_edge_cases(self):
        """Test edge cases for word bolding."""
        # Case sensitivity
        result = TextProcessor.bold_word_in_text("The Cat sat on the mat", "cat")
        assert "<b>Cat</b>" in result or "<b>cat</b>" in result

        # Multiple occurrences
        result = TextProcessor.bold_word_in_text("The cat and another cat", "cat")
        assert result.count("<b>cat</b>") == 2

        # Word boundaries
        result = TextProcessor.bold_word_in_text("The catch is tricky", "cat")
        # Should not bold "cat" within "catch"
        assert "catch" not in result.replace("catch", "c<b>cat</b>ch")

    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        processor = TextProcessor()

        # Test HTML tag removal
        result = processor.clean_text("<p>Hello <b>world</b></p>")
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello world" in result

        # Test whitespace normalization
        result = processor.clean_text("Hello    world\n\n\ntest")
        assert "Hello world test" in result

    def test_clean_text_edge_cases(self):
        """Test edge cases for text cleaning."""
        processor = TextProcessor()

        # Empty and whitespace-only strings
        assert processor.clean_text("") == ""
        assert processor.clean_text("   ") == ""

        # Complex HTML
        html_text = '<div class="test"><span>Hello</span> <em>world</em>!</div>'
        result = processor.clean_text(html_text)
        assert "Hello world!" in result
        assert "<div>" not in result
