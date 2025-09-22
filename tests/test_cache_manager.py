from anki_connector.models.cache_models import CacheConfig
from anki_connector.models.word_info import (
    Phonetics,
    WordDefinition,
    WordForms,
    WordInfo,
)
from anki_connector.utils.cache_engine import CacheEngine
from anki_connector.utils.cache_manager import CacheManager


def sample_word_info() -> WordInfo:
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


def test_cache_set_get_roundtrip(tmp_path):
    # Use the cache manager directly for set/get roundtrip
    cfg = CacheConfig(ttl_days=1, max_size_mb=10)
    cm = CacheEngine(cfg, tmp_path)
    wi = sample_word_info()
    key = cm.get_cache_key(wi.word)
    cm.set(key, wi.model_dump())
    out = cm.get(key)
    assert out and out["word"] == "example"


def test_check_audio_cache(tmp_path):
    # create dummy us/uk files
    (tmp_path / "example_us.mp3").write_bytes(b"\x00")
    (tmp_path / "example_uk_youdao.mp3").write_bytes(b"\x00")
    cm = CacheManager(audio_dir=str(tmp_path))
    status = cm.check_audio_cache("example")
    assert status["us_exists"] is True
    assert status["uk_exists"] is True
