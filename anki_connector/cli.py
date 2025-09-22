"""Modern command line interface for Anki Vocabulary Tool"""

import argparse
import sys
from pathlib import Path

from .config.settings import settings
from .core.factory import create_vocabulary_processor
from .core.vocabulary_processor import BatchProcessingResult
from .exceptions import AnkiVocabError
from .logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def clear_vocabulary_cache() -> None:
    """Clear the layered cache (memory+disk)."""
    from .models.cache_models import CacheConfig
    from .utils.cache_engine import CacheEngine

    cfg = CacheConfig(
        ttl_days=settings.cache.ttl_days, max_size_mb=settings.cache.max_size_mb
    )
    cm = CacheEngine(cfg, settings.cache.dir)
    cm.clear()
    logger.info("✅ Cache cleared: memory and disk index/files")


def clear_cache_entries(words: list[str]) -> None:
    """Clear cache entries for specific words."""
    if not words:
        return
    from .models.cache_models import CacheConfig
    from .utils.cache_engine import CacheEngine

    cfg = CacheConfig(
        ttl_days=settings.cache.ttl_days, max_size_mb=settings.cache.max_size_mb
    )
    cm = CacheEngine(cfg, settings.cache.dir)
    removed = 0
    for w in words:
        key = cm.get_cache_key(w)
        if cm.delete(key):
            removed += 1
            logger.info(f"🧹 Removed cache: {w}")
    if removed == 0:
        logger.info("ℹ️ No matching cache entries were found for the specified words")


def _available_themes() -> list[str]:
    """Discover available packaged themes under templates/themes/* that are valid.

    A valid theme directory must contain: front.html.j2, back.html.j2, style.css.j2
    Returns a sorted list of theme names. If none found, returns [].
    """
    try:
        base = Path(__file__).resolve().parent / "templates" / "themes"
        if not base.exists():
            return []
        required = {"front.html.j2", "back.html.j2", "style.css.j2"}
        names: list[str] = []
        for p in base.iterdir():
            if not p.is_dir():
                continue
            files = {child.name for child in p.iterdir() if child.is_file()}
            if required.issubset(files):
                names.append(p.name)
        return sorted(names)
    except Exception:
        return []


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser"""
    prog_name = Path(sys.argv[0]).name
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description="Modern vocabulary importer for Anki with audio support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ankic word1 word2 word3          # Process individual words
  ankic my_words.txt               # Process words from a .txt file (positional)
  ankic word1 words.txt word2      # Mix words and files together
  ankic --deck MyDeck word1 word2  # Use custom deck name
  ankic --stats                    # Show processing statistics
  ankic --list-themes              # List available card themes
        """,
    )

    # Main arguments (words or .txt files; mixed allowed)
    parser.add_argument("words", nargs="*", help="Words and/or .txt files to process")
    parser.add_argument(
        "-d",
        "--deck",
        default=settings.anki.deck_name,
        help=f"Anki deck name (default: {settings.anki.deck_name})",
    )

    # Audio options
    audio_group = parser.add_argument_group("audio options")
    audio_group.add_argument(
        "--no-audio", action="store_true", help="Skip audio download"
    )
    audio_group.add_argument(
        "--interval",
        type=float,
        default=settings.audio.delay,
        help=f"Delay between operations in seconds (default: {settings.audio.delay})",
    )

    # Processing options
    processing_group = parser.add_argument_group("processing options")
    processing_group.add_argument(
        "--force-update", action="store_true", help="Force update existing cards"
    )
    processing_group.add_argument(
        "--max-workers",
        type=int,
        default=settings.max_workers,
        help=f"Maximum worker threads (default: {settings.max_workers})",
    )

    # Cache options
    cache_group = parser.add_argument_group("cache options")
    cache_group.add_argument(
        "--clear-cache",
        nargs="*",
        metavar="WORD",
        help=(
            "Clear vocabulary cache. Without words clears all; with WORD(s) clears only those entries"
        ),
    )

    # Information options
    info_group = parser.add_argument_group("information options")
    info_group.add_argument(
        "--stats", action="store_true", help="Show processing statistics"
    )
    info_group.add_argument(
        "--cache-stats", action="store_true", help="Show cache statistics"
    )

    # Logging options
    log_group = parser.add_argument_group("logging options")
    log_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    log_group.add_argument("--debug", action="store_true", help="Enable debug logging")
    log_group.add_argument("--log-file", type=Path, help="Write logs to file")

    # Template options
    tmpl_group = parser.add_argument_group("template options")
    themes = _available_themes()
    tmpl_help_suffix = f" Available: {', '.join(themes)}" if themes else ""
    tmpl_group.add_argument(
        "-t",
        "--template",
        choices=themes if themes else None,
        default=None,
        help=(
            "Card theme to use. If omitted, uses built-in default: vapor."
            + tmpl_help_suffix
        ),
    )
    tmpl_group.add_argument(
        "--list-themes",
        action="store_true",
        help="List available card themes and exit",
    )

    return parser


def print_batch_results(result: BatchProcessingResult) -> None:
    """Print formatted batch processing results"""
    print("\n" + "=" * 60)
    print("📊 PROCESSING SUMMARY")
    print("=" * 60)

    print(f"Total words processed: {result.total_processed}")
    print(f"✅ Successful: {result.successful}")
    print(f"❌ Failed: {result.failed}")
    print(f"⏭️ Skipped: {result.skipped}")
    print(f"📈 Success rate: {result.success_rate:.1f}%")

    if result.failed > 0:
        # Comma-separated list to keep output concise
        failed_words = [res.word for res in result.results if not res.success]
        if failed_words:
            print("\n❌ Failed words: " + ", ".join(failed_words))
        if result.errors:
            # Summarize reasons in a single line (unique, non-empty)
            reasons = [e for e in result.errors if e]
            if reasons:
                unique = list(dict.fromkeys(reasons))
                print(f"Reason: {'; '.join(unique)}")

    if result.skipped > 0:
        print("\n⏭️ Skipped words:")
        for res in result.results:
            if res.skipped_reason:
                print(f"  - {res.word}: {res.skipped_reason}")

    print("=" * 60)


def _is_text_file(path: Path, sample_size: int = 4096) -> bool:
    """Heuristic to detect text files via magic bytes + UTF-8 decoding.

    - Only .txt is allowed; this function checks content looks like text.
    - Detects common binary signatures (PDF, PNG, JPEG, ZIP, GZIP, ELF, EXE, MP3, OGG, etc.).
    """
    if not path.is_file():
        return False
    # Read sample
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
    except Exception:
        return False

    # Common binary magic signatures
    signatures = (
        b"%PDF-",  # PDF
        b"\x89PNG\r\n\x1a\n",  # PNG
        b"\xff\xd8\xff",  # JPEG
        b"GIF8",  # GIF
        b"PK\x03\x04",  # ZIP/OOXML
        b"\x1f\x8b\x08",  # GZIP
        b"MZ",  # Windows EXE/DLL
        b"\x7fELF",  # ELF
        b"OggS",  # OGG
        b"ID3",  # MP3 (ID3 tag)
    )
    for sig in signatures:
        if chunk.startswith(sig):
            return False
    if b"\x00" in chunk:
        return False

    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _classify_inputs(args: argparse.Namespace) -> tuple[list[str], list[Path]]:
    """Classify positional inputs into words vs .txt files (by existence + magic)."""
    words: list[str] = []
    files: list[Path] = []
    for token in args.words:
        p = Path(token)
        if p.exists() and p.is_file():
            if p.suffix.lower() != ".txt":
                logger.error(
                    f"Unsupported file type for '{token}'. Only .txt is allowed."
                )
                continue
            if not _is_text_file(p):
                logger.error(f"File '{token}' is not a valid UTF-8 text file.")
                continue
            files.append(p)
        else:
            # If it looks like a .txt file but doesn't exist, ignore it
            if p.suffix.lower() == ".txt":
                logger.error(f"File not found (ignored): {token}")
                continue
            words.append(token)
    return words, files


def process_words_main(args: argparse.Namespace) -> None:
    """Process words from command line arguments"""
    # Classify inputs into words vs .txt files (existence + magic head)
    word_args, file_args = _classify_inputs(args)

    logger.info(f"Processing {len(word_args)} words and {len(file_args)} files")
    if word_args:
        logger.debug(f"Words: {', '.join(word_args)}")
    if file_args:
        logger.debug(f"Files: {', '.join(str(p) for p in file_args)}")

    try:
        processor = create_vocabulary_processor(
            deck_name=args.deck, template=args.template
        )
        logger.info(f"Target deck: {args.deck}")
        logger.info(
            f"Target model: {processor.model_name}"
            + (f" (theme: {args.template})" if args.template else "")
        )
        logger.info(f"Audio: {'enabled' if not args.no_audio else 'disabled'}")

        results: list[BatchProcessingResult] = []

        if word_args:
            results.append(
                processor.process_word_list(
                    word_args,
                    include_audio=not args.no_audio,
                    delay=args.interval,
                    force_update=args.force_update,
                )
            )

        for f in file_args:
            if not f.exists():
                logger.error(f"File not found: {f}")
                continue
            results.append(
                processor.process_file(
                    str(f),
                    include_audio=not args.no_audio,
                    delay=args.interval,
                    force_update=args.force_update,
                )
            )

        # Merge results and print summary
        merged = merge_results(results)
        print_batch_results(merged)

        # Show statistics if requested
        if args.stats:
            stats = processor.get_statistics()
            print("\n📈 Processing Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

        print(f"\n💡 Check your Anki deck: {args.deck}")

        # Exit with error code if there were failures
        if merged.failed > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error processing words: {e}")
        raise AnkiVocabError(f"Failed to process words: {e}") from e


def merge_results(results: list[BatchProcessingResult]) -> BatchProcessingResult:
    """Merge multiple batch results into one summary."""
    if not results:
        return BatchProcessingResult(0, 0, 0, 0, [], [])

    total_processed = sum(r.total_processed for r in results)
    successful = sum(r.successful for r in results)
    failed = sum(r.failed for r in results)
    skipped = sum(r.skipped for r in results)
    merged_results: list = []
    merged_errors: list[str] = []
    for r in results:
        merged_results.extend(r.results)
        merged_errors.extend(r.errors)
    return BatchProcessingResult(
        total_processed, successful, failed, skipped, merged_results, merged_errors
    )


def show_cache_stats() -> None:
    """Show cache statistics"""
    from .models.cache_models import CacheConfig
    from .utils.cache_engine import CacheEngine

    config = CacheConfig(
        ttl_days=settings.cache.ttl_days, max_size_mb=settings.cache.max_size_mb
    )

    cache_manager = CacheEngine(config, settings.cache.dir)
    stats = cache_manager.get_stats()

    print("\n📊 CACHE STATISTICS")
    print("=" * 40)
    print(f"Total entries: {stats.total_entries}")
    print(f"Valid entries: {stats.valid_entries}")
    print(f"Expired entries: {stats.expired_entries}")
    print(f"Cache size: {stats.cache_size_mb:.2f} MB")
    print(f"Hit rate: {stats.hit_rate:.1f}%")
    print("=" * 40)


def main() -> None:
    """Main entry point for the CLI"""
    parser = create_parser()

    # Handle no arguments case
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else ("DEBUG" if args.verbose else "INFO")
    log_file = str(args.log_file) if args.log_file else None
    setup_logging(log_level, log_file)

    try:
        logger.debug("🚀 Enhanced Anki Vocabulary Tool started")

        # Handle list themes command
        if getattr(args, "list_themes", False):
            themes = _available_themes()
            if themes:
                print("\n🎨 Available themes:")
                for name in themes:
                    print(f"  - {name}")
            else:
                print("\nNo packaged themes found.")
            return

        # Handle cache stats command
        if args.cache_stats:
            show_cache_stats()
            return

        # Handle clear cache command
        if args.clear_cache is not None:
            if len(args.clear_cache) == 0:
                clear_vocabulary_cache()
            else:
                clear_cache_entries(args.clear_cache)
            if not args.words:  # Exit if only clearing cache
                return

        # Validate arguments
        if not args.words and not args.stats:
            parser.error("Provide words and/or .txt files, or use --stats")

        # Handle stats only
        if args.stats and not args.words:
            # Show general stats without processing
            print(
                "No processing performed. Use with words or .txt files to see processing stats."
            )
            return

        # Process mixed words/files
        process_words_main(args)

        logger.info("✅ Processing completed successfully")

    except AnkiVocabError as e:
        logger.error(f"Application error: {e}")
        if args.debug:
            logger.exception("Full traceback:")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.debug or args.verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
