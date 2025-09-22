"""Tests for parsing Vocabulary.com AJAX HTML fixtures.

Note: Only tests AJAX response parsing since full HTML requests were removed.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from anki_connector.core.vocabulary_fetcher import VocabularyFetcher


def load_fixture(name: str) -> BeautifulSoup:
    # Look for AJAX result fixtures
    here = Path(__file__).resolve().parent
    candidates = [
        here
        / "source"
        / f"vocab_word_{name.lower()}_ajax_result.html",  # tests/source/vocab_word_<name>_ajax_result.html
    ]
    for p in candidates:
        if p.exists():
            return BeautifulSoup(
                p.read_text(encoding="utf-8", errors="ignore"), "html.parser"
            )
    raise FileNotFoundError(f"Fixture not found for {name}: {candidates}")


def assert_common_structure(data: dict):
    assert isinstance(data, dict)
    # Must have the canonical keys
    for key in ("word", "phonetics", "parts", "exchanges", "additions"):
        assert key in data
    # parts is a list of senses
    assert isinstance(data["parts"], list)


def test_buffer_ajax_fixture_parses():
    soup = load_fixture("Buffer")
    f = VocabularyFetcher()
    data = f._parse_vocab_soup(soup)
    assert_common_structure(data)
    # Buffer has multiple definitions with different parts of speech
    assert (
        len(data["parts"]) >= 3
    ), "Buffer should have at least 3 different definitions"

    # Verify that we get both verb and noun definitions
    parts_of_speech = [part.get("part", "").lower() for part in data["parts"]]
    assert "verb" in parts_of_speech, "Buffer should have verb definitions"
    assert "noun" in parts_of_speech, "Buffer should have noun definitions"

    # Check that we have phonetics information
    phonetics = data.get("phonetics", [])
    assert len(phonetics) > 0, "Buffer should have pronunciation info"
    # Should have both US and UK pronunciation
    phonetics_text = " ".join(phonetics).lower()
    assert (
        "us:" in phonetics_text and "uk:" in phonetics_text
    ), "Should have both US and UK pronunciations"


def test_project_ajax_fixture_parses():
    """Test that project word parsing includes both noun and verb definitions"""
    soup = load_fixture("Project")
    f = VocabularyFetcher()
    data = f._parse_vocab_soup(soup)
    assert_common_structure(data)

    # Project should have multiple definitions with different parts of speech
    assert (
        len(data["parts"]) >= 5
    ), f"Project should have at least 5 different definitions, got {len(data['parts'])}"

    # Verify that we get both noun and verb definitions
    parts_of_speech = [part.get("part", "").lower() for part in data["parts"]]
    print(f"Found parts of speech: {parts_of_speech}")

    assert "noun" in parts_of_speech, "Project should have noun definitions"
    assert "verb" in parts_of_speech, "Project should have verb definitions"

    # Count how many of each we have
    noun_count = parts_of_speech.count("noun")
    verb_count = parts_of_speech.count("verb")

    print(f"Found {noun_count} noun definitions and {verb_count} verb definitions")

    assert (
        noun_count >= 3
    ), f"Project should have at least 3 noun definitions, got {noun_count}"
    assert (
        verb_count >= 5
    ), f"Project should have at least 5 verb definitions, got {verb_count}"

    # Check that we have phonetics information
    phonetics = data.get("phonetics", [])
    print(f"Found phonetics: {phonetics}")
    assert (
        len(phonetics) >= 2
    ), f"Project should have at least 2 pronunciations, got {len(phonetics)}"

    # Test the complete conversion to WordInfo
    word_info = f._dict_to_word_info(data)
    print(f"US phonetic: {word_info.phonetics.us}")
    print(f"UK phonetic: {word_info.phonetics.uk}")

    # Both phonetic fields should have values
    assert word_info.phonetics.us is not None, "US phonetic should not be None"
    assert word_info.phonetics.uk is not None, "UK phonetic should not be None"


def test_design_ajax_fixture_parses():
    """Test that design word AJAX parsing works correctly"""
    soup = load_fixture("Design")
    f = VocabularyFetcher()
    data = f._parse_vocab_soup(soup)
    assert_common_structure(data)

    # Design should have multiple definitions
    assert (
        len(data["parts"]) >= 2
    ), f"Design should have at least 2 definitions, got {len(data['parts'])}"

    # Check that we have phonetics information
    phonetics = data.get("phonetics", [])
    assert len(phonetics) > 0, "Design should have pronunciation info"
