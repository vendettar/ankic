"""Main vocabulary processor using dependency injection and modern architecture"""

import time
from dataclasses import dataclass
from typing import Any

from ..config.settings import settings
from ..exceptions import (
    AnkiOperationError,
    AnkiVocabError,
    WordNotFoundError,
    WordValidationError,
)
from ..logging_config import get_logger
from ..models.word_info import WordInfo
from ..models.word_models import AudioFiles
from ..templates.card_template import VocabularyCardTemplate
from ..templates.loader import load_card_visuals
from ..utils.error_handler import ErrorCollector, handle_errors
from .interfaces import (
    AnkiClientInterface,
    AudioDownloaderInterface,
    CacheManagerInterface,
    TextProcessorInterface,
    VocabularyFetcherInterface,
)

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    """Result of word processing operation"""

    word: str
    success: bool
    note_id: int | None = None
    error: str | None = None
    was_updated: bool = False
    skipped_reason: str | None = None


@dataclass
class BatchProcessingResult:
    """Result of batch processing operation"""

    total_processed: int
    successful: int
    failed: int
    skipped: int
    results: list[ProcessingResult]
    errors: list[str]

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_processed == 0:
            return 0.0
        return (self.successful / self.total_processed) * 100


class VocabularyProcessor:
    """Main vocabulary processor with dependency injection"""

    def __init__(
        self,
        vocabulary_fetcher: VocabularyFetcherInterface,
        audio_downloader: AudioDownloaderInterface,
        anki_client: AnkiClientInterface,
        cache_manager: CacheManagerInterface,
        text_processor: TextProcessorInterface,
        deck_name: str | None = None,
        template_spec: str | None = None,
        enrichers: list[Any] | None = None,
    ):
        # Injected dependencies
        self.vocabulary_fetcher = vocabulary_fetcher
        self.audio_downloader = audio_downloader
        self.anki_client = anki_client
        self.cache_manager = cache_manager
        self.text_processor = text_processor
        self._enrichers = enrichers or []

        # Configuration
        self.deck_name = deck_name or settings.anki.deck_name

        # Card visuals/config
        # - Defines required fields
        # - Provides default front/back/CSS (overridable via --template)
        self._template_spec = template_spec
        # Derive model name: if a template is specified, create a per-theme model
        # so that updating one theme doesn't affect decks using another theme.
        self.model_name = self._derive_model_name()
        self.card_template = VocabularyCardTemplate(self.model_name)

        # Statistics
        self._stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "audio_downloads": 0,
            "anki_operations": 0,
        }

    @handle_errors(default_return=False, operation_name="setup_anki_environment")
    def setup_anki_environment(self) -> bool:
        """Setup Anki deck and card type"""
        try:
            # Fast path for tests/CI to avoid heavy template/rendering and API calls
            if getattr(settings, "fast_mode", False):
                return True
            # Create deck
            if not self.anki_client.create_deck(self.deck_name):
                logger.error(f"Failed to create deck: {self.deck_name}")
                return False

            # Setup card type using existing template system
            model_names = self.anki_client.get_model_names()
            card_config = self.card_template.create_card_type()

            # Override visuals if a template was provided
            try:
                override = load_card_visuals(self._template_spec)
            except FileNotFoundError as e:
                logger.warning(f"Template not found: {e}; using default visuals")
                override = None
            except Exception as e:
                logger.warning(
                    f"Failed to load template '{self._template_spec}': {e}; using default visuals"
                )
                override = None

            if override:
                front, back, css = override
                card_config["front_template"] = front
                card_config["back_template"] = back
                card_config["css"] = css

            if self.model_name not in model_names:
                # Create new model
                fields = [field["name"] for field in card_config["fields"]]
                templates = [
                    {
                        "Name": "AnkicCard",
                        "Front": card_config["front_template"],
                        "Back": card_config["back_template"],
                    }
                ]

                if not self.anki_client.create_model(
                    self.model_name, fields, card_config["css"], templates
                ):
                    logger.error(f"Failed to create card type: {self.model_name}")
                    return False
            else:
                # Update existing model
                self.anki_client.update_model_templates(
                    self.model_name,
                    card_config["css"],
                    [
                        {
                            "Name": "AnkicCard",
                            "Front": card_config["front_template"],
                            "Back": card_config["back_template"],
                        }
                    ],
                )
                # Ensure all required fields exist
                fields = [field["name"] for field in card_config["fields"]]
                self.anki_client.ensure_model_fields(self.model_name, fields)

            return True

        except Exception as e:
            logger.error(f"Failed to setup Anki environment: {e}")
            raise AnkiOperationError("setup_environment", str(e)) from e

    def validate_word(self, word: str) -> str:
        """Validate and clean word input"""
        if not word:
            raise WordValidationError(word, "Word cannot be empty")

        cleaned_word = self.text_processor.clean_word(word)
        if not cleaned_word:
            raise WordValidationError(word, "Invalid word format")

        return cleaned_word.lower()

    def check_card_exists(self, word: str) -> int | None:
        """Check if a card already exists in the target deck"""
        search_queries = [
            f'deck:"{self.deck_name}" Word:"{word}"',
            f"deck:{self.deck_name} Word:{word}",
        ]

        for query in search_queries:
            notes = self.anki_client.find_notes(query)
            # Be defensive: only treat as found when a real non-empty list is returned
            if isinstance(notes, list) and len(notes) > 0:
                return notes[0]  # Return note ID

        return None

    @handle_errors(default_return=None, operation_name="fetch_word_info")
    def fetch_word_info(self, word: str) -> WordInfo | None:
        """Fetch word information with caching"""
        # Check cache first
        cached_data = self.cache_manager.get_cached_word_info(word)
        if cached_data:
            logger.debug(f"Cache hit for word: {word}")
            self._stats["cache_hits"] += 1
            return cached_data

        # Fetch fresh data
        logger.debug(f"Cache miss for word: {word}, fetching from source")
        self._stats["cache_misses"] += 1

        word_info = self.vocabulary_fetcher.fetch_word_info(word)
        if not word_info:
            raise WordNotFoundError(word, ["vocabulary.com"])

        # Cache the data
        self.cache_manager.cache_word_info(word, word_info)
        return word_info

    def _derive_model_name(self) -> str:
        """Return the Anki model name, isolating per theme when specified.

        - If no template is specified, use the base configured model name for
          backward compatibility.
        - If a template is provided, append a sanitized theme label so models
          with different themes don't overwrite each other's styling.
        """
        base = settings.anki.model_name
        if not self._template_spec:
            return base

        # Determine theme label from template spec (name or filesystem path)
        try:
            from pathlib import Path

            p = Path(self._template_spec)
            if p.exists() and p.is_dir():
                label = p.name
            else:
                label = str(self._template_spec)
        except Exception:
            label = str(self._template_spec)

        # Sanitize label for model name (keep letters, digits, space, - _)
        import re

        clean = re.sub(r"[^\w\- ]+", " ", label).strip()
        clean = re.sub(r"\s+", " ", clean)

        # Compose final model name
        return f"{base} [{clean}]"

    @handle_errors(default_return=None, operation_name="download_audio")
    def download_audio(self, word: str) -> AudioFiles | None:
        """Download audio files for a word"""
        # Check if audio already exists
        audio_status = self.audio_downloader.check_audio_exists(word)
        if audio_status.get("us_exists") and audio_status.get("uk_exists"):
            logger.debug(f"Audio files already exist for: {word}")
            return AudioFiles(us_audio=f"{word}_us.mp3", uk_audio=f"{word}_uk.mp3")

        # Download missing audio
        logger.debug(f"Downloading audio for: {word}")
        self._stats["audio_downloads"] += 1
        return self.audio_downloader.download_word_audio(word)

    def convert_to_card_data(self, word_info: WordInfo) -> dict[str, str]:
        """Convert WordInfo to Anki card data format"""
        card_data = {}

        # 1. Basic word info fields
        basic_data = {
            "Word": word_info.word,
            "USPhonetic": word_info.phonetics.us or "",
            "UKPhonetic": word_info.phonetics.uk or "",
            "USAudio": "",
            "UKAudio": "",
        }
        card_data.update(basic_data)

        # 2. Vocabulary fields
        vocab_data = {
            "VocabWordForms": ", ".join(word_info.word_forms.forms),
            "VocabShortExplanation": word_info.short_explanation or "",
            "VocabLongExplanation": word_info.long_explanation or "",
        }

        # Initialize vocabulary entry fields (structured format like MW)
        for i in range(1, 26):
            vocab_data[f"VocabEntry{i}"] = ""

        card_data.update(vocab_data)

        # 3. General fields
        general_data = {
            "Etymology": "",
            "Tags": "vocabulary",
        }
        card_data.update(general_data)

        # Fill in vocabulary entries (part of speech + definition in one field)
        for i, definition in enumerate(word_info.definitions[:25], 1):
            # Get abbreviated part of speech
            pos = self.text_processor.abbreviate_part_of_speech(
                definition.part_of_speech
            )

            # Build definition text with examples and synonyms
            definition_text = self.text_processor.clean_text(definition.definition)

            # Add examples (use as-is from source, no extra quotes)
            if definition.examples:
                example = self.text_processor.clean_text(definition.examples[0])
                if example:
                    # Bold the word in example
                    example = self.text_processor.bold_word_in_text(
                        example, word_info.word
                    )
                    definition_text += f'\n<br><em class="example">{example}</em>'

            # Add synonyms and antonyms
            if definition.synonyms:
                synonyms = ", ".join(definition.synonyms[:6])
                definition_text += (
                    f'\n<br><span class="synonyms">Synonyms: {synonyms}</span>'
                )

            if definition.antonyms:
                antonyms = ", ".join(definition.antonyms[:6])
                definition_text += (
                    f'\n<br><span class="antonyms">Antonyms: {antonyms}</span>'
                )

            # Combine part of speech and definition (like MW format)
            if pos:
                entry_html = (
                    f'<span class="vocab-part-of-speech">{pos}</span> {definition_text}'
                )
            else:
                entry_html = definition_text

            card_data[f"VocabEntry{i}"] = entry_html

        return card_data

    @handle_errors(default_return=None, operation_name="process_single_word")
    def process_word(
        self, word: str, include_audio: bool = True, force_update: bool = False
    ) -> ProcessingResult:
        """Process a single word into an Anki card"""
        try:
            # Validate word
            clean_word = self.validate_word(word)
            logger.info(f"Processing word: {clean_word}")

            # Check if card already exists
            existing_note_id = self.check_card_exists(clean_word)
            if existing_note_id and not force_update:
                logger.info(f"Card already exists for: {clean_word}")
                return ProcessingResult(
                    word=clean_word,
                    success=True,
                    note_id=existing_note_id,
                    skipped_reason="already_exists",
                )

            # Fetch word information
            word_info = self.fetch_word_info(clean_word)
            if not word_info:
                return ProcessingResult(
                    word=clean_word,
                    success=False,
                    error="Failed to fetch word information (possible network/timeout)",
                )

            # Convert to card data
            card_data = self.convert_to_card_data(word_info)
            # Apply optional enrichers (e.g., Merriam‑Webster) to add fields
            try:
                for enricher in self._enrichers:
                    extra = getattr(enricher, "enrich", None)
                    if callable(extra):
                        more = extra(clean_word, word_info)
                        if isinstance(more, dict):
                            card_data.update(
                                {k: v for k, v in more.items() if isinstance(v, str)}
                            )
            except Exception as e:
                logger.debug(f"Content enrichment skipped due to error: {e}")

            # Handle audio (only if globally enabled and requested)
            if include_audio and settings.audio.enable_audio:
                audio_files = self.download_audio(clean_word)
                if audio_files:
                    # Upload to Anki
                    anki_audio = self.anki_client.store_word_audio_files(
                        clean_word, str(settings.audio.dir)
                    )
                    # Update audio fields using consistent pattern
                    audio_data = {
                        "USAudio": anki_audio.us_audio or "",
                        "UKAudio": anki_audio.uk_audio or "",
                    }
                    card_data.update(audio_data)

            # Add or update note in Anki
            self._stats["anki_operations"] += 1
            if existing_note_id and force_update:
                # Update existing note
                success = self.anki_client.update_note_fields(
                    existing_note_id, card_data
                )
                if success:
                    logger.info(f"Updated card for: {clean_word}")
                    return ProcessingResult(
                        word=clean_word,
                        success=True,
                        note_id=existing_note_id,
                        was_updated=True,
                    )
                else:
                    return ProcessingResult(
                        word=clean_word,
                        success=False,
                        error="Failed to update Anki note",
                    )
            else:
                # Add new note
                note_id = self.anki_client.add_note(
                    self.deck_name,
                    self.model_name,
                    card_data,
                    ["vocabulary", "auto-import"],
                )
                if note_id:
                    logger.info(f"✅ Added card for: {clean_word}")
                    return ProcessingResult(
                        word=clean_word, success=True, note_id=note_id
                    )
                else:
                    return ProcessingResult(
                        word=clean_word, success=False, error="Failed to add Anki note"
                    )

        except WordValidationError as e:
            return ProcessingResult(
                word=word, success=False, error=f"Validation error: {e.reason}"
            )
        except WordNotFoundError as e:
            return ProcessingResult(
                word=word,
                success=False,
                error=f"Word not found in sources: {', '.join(e.attempted_sources)}",
            )
        except AnkiVocabError as e:
            return ProcessingResult(word=word, success=False, error=str(e))
        except Exception as e:
            logger.error(f"Unexpected error processing {word}: {e}")
            return ProcessingResult(
                word=word, success=False, error=f"Unexpected error: {e}"
            )

    def process_word_list(
        self,
        words: list[str],
        include_audio: bool = True,
        delay: float | None = None,
        force_update: bool = False,
    ) -> BatchProcessingResult:
        """Process a list of words"""
        if delay is None:
            delay = settings.audio.delay

        if not self.setup_anki_environment():
            # Emit a per-word failure so the CLI can list the failed words
            failed_results = [
                ProcessingResult(
                    word=str(w),
                    success=False,
                    error="Anki environment not available (create deck/model failed)",
                )
                for w in words
            ]
            return BatchProcessingResult(
                total_processed=len(words),
                successful=0,
                failed=len(words),
                skipped=0,
                results=failed_results,
                errors=["Failed to setup Anki environment"],
            )

        logger.info(f"Processing {len(words)} words...")
        logger.info(f"Deck: {self.deck_name}")
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Audio: {'enabled' if include_audio else 'disabled'}")
        logger.info("=" * 60)

        results = []
        error_collector = ErrorCollector()

        for i, word in enumerate(words, 1):
            logger.debug(f"({i}/{len(words)}) Processing: {word}")

            try:
                result = self.process_word(word, include_audio, force_update)
                results.append(result)

                if result.success:
                    if result.skipped_reason:
                        logger.info(f"  ✅ Skipped ({result.skipped_reason})")
                    elif result.was_updated:
                        logger.info("  ✅ Updated")
                    # Note: "Added" case is already logged in _process_single_word
                    pass
                else:
                    logger.warning(f"  ❌ Failed: {result.error}")
                    error_collector.add_error(Exception(f"{word}: {result.error}"))

            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                error_collector.add_error(e)
                results.append(ProcessingResult(word=word, success=False, error=str(e)))

            # Rate limiting only when audio is in use
            if (
                include_audio
                and settings.audio.enable_audio
                and i < len(words)
                and (delay or 0) > 0
            ):
                time.sleep(delay)

        # Calculate statistics
        successful = sum(1 for r in results if r.success and not r.skipped_reason)
        skipped = sum(1 for r in results if r.skipped_reason)
        failed = len(results) - successful - skipped

        logger.info("=" * 60)
        logger.info(
            f"Completed: {successful} successful, {failed} failed, {skipped} skipped"
        )

        # Log any collected errors
        if error_collector.has_errors():
            error_collector.log_all(logger)

        return BatchProcessingResult(
            total_processed=len(words),
            successful=successful,
            failed=failed,
            skipped=skipped,
            results=results,
            errors=[str(e) for e in error_collector.errors],
        )

    def process_file(
        self,
        file_path: str,
        include_audio: bool = True,
        delay: float | None = None,
        force_update: bool = False,
    ) -> BatchProcessingResult:
        """Process words from a text file"""
        try:
            with open(file_path, encoding="utf-8") as f:
                words: list[str] = []
                content = f.read()
                for raw in content.splitlines():
                    raw = raw.strip()
                    # Skip empty lines and comments
                    if not raw or raw.startswith("#"):
                        continue
                    # Validate and normalize using the text processor
                    cleaned = self.text_processor.clean_word(raw)
                    if cleaned:
                        words.append(cleaned)

            return self.process_word_list(words, include_audio, delay, force_update)

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return BatchProcessingResult(
                total_processed=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                errors=[f"File not found: {file_path}"],
            )
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return BatchProcessingResult(
                total_processed=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                errors=[f"Error reading file: {e}"],
            )

    def get_statistics(self) -> dict[str, Any]:
        """Get processing statistics"""
        return {
            **self._stats,
            "cache_hit_rate": (
                self._stats["cache_hits"]
                / (self._stats["cache_hits"] + self._stats["cache_misses"])
                * 100
                if (self._stats["cache_hits"] + self._stats["cache_misses"]) > 0
                else 0
            ),
        }
