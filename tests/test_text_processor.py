from anki_connector.core.text_processor import TextProcessor


def test_is_valid_word_basic():
    assert TextProcessor.is_valid_word("hello")
    assert TextProcessor.is_valid_word("state-of-the-art")
    assert not TextProcessor.is_valid_word("")
    assert not TextProcessor.is_valid_word("foo.txt")
    assert not TextProcessor.is_valid_word("/etc/passwd")


def test_clean_word_normalizes_spaces_and_validates():
    assert TextProcessor.clean_word("  Hello   World ") == "Hello World"
    assert TextProcessor.clean_word("foo.txt") is None


def test_extract_phonetic():
    assert TextProcessor.extract_phonetic("US: /həˈloʊ/") == "/həˈloʊ/"
    assert TextProcessor.extract_phonetic("/kæt/") == "/kæt/"


def test_abbreviate_pos():
    assert TextProcessor.abbreviate_part_of_speech("noun") == "n."
    assert TextProcessor.abbreviate_part_of_speech("adjective") == "adj."
    # substring fallback
    assert TextProcessor.abbreviate_part_of_speech("transitive verb") in ("v.", "vt.")


def test_bold_word_in_text():
    out = TextProcessor.bold_word_in_text("A cat is not a dog", "cat")
    assert "<b>cat</b>" in out
