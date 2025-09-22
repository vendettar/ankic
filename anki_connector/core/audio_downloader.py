"""Audio file downloader for word pronunciations"""

import os
import time
from urllib.parse import quote

import requests  # type: ignore[import-untyped]
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util import Retry

from ..config.settings import settings
from ..logging_config import get_logger
from ..models.word_models import AudioFiles
from .constants import AudioConstants, get_audio_patterns
from .interfaces import AudioDownloaderInterface

logger = get_logger(__name__)


class AudioDownloader(AudioDownloaderInterface):
    """Downloads pronunciation audio files from various TTS services"""

    def __init__(self, audio_dir: str | None = None, timeout: int | None = None):
        self.audio_dir = audio_dir or str(settings.audio.dir)
        self.timeout = int(
            timeout if timeout is not None else settings.anki.request_timeout
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": AudioConstants.AUDIO_USER_AGENT})
        self._ensure_audio_directory()
        self._configure_retries()

    def _configure_retries(self) -> None:
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _ensure_audio_directory(self) -> str:
        """Create audio directory if it doesn't exist"""
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)
        return self.audio_dir

    def download_google_tts(self, word: str, accent: str = "us") -> str | None:
        """Download audio from Google TTS"""
        if settings.audio.offline:
            return None
        try:
            if accent.lower() == "us":
                url = AudioConstants.GOOGLE_TTS_US_URL.format(word=quote(word))
            else:  # UK
                url = AudioConstants.GOOGLE_TTS_UK_URL.format(word=quote(word))

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            filename = f"{word}_{accent}.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            with open(filepath, "wb") as f:
                f.write(response.content)

            return filename

        except requests.RequestException as e:
            logger.warning(f"Network error downloading {accent} audio for {word}: {e}")
            return None
        except OSError as e:
            logger.warning(
                f"File system error downloading {accent} audio for {word}: {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading {accent} audio for {word}: {e}")
            return None

    def download_youdao_tts(self, word: str, accent: str = "us") -> str | None:
        """Download audio from Youdao TTS"""
        if settings.audio.offline:
            return None
        try:
            if accent.lower() == "us":
                url = AudioConstants.YOUDAO_TTS_US_URL.format(word=quote(word))
            else:  # UK
                url = AudioConstants.YOUDAO_TTS_UK_URL.format(word=quote(word))

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            filename = f"{word}_{accent}_youdao.mp3"
            filepath = os.path.join(self.audio_dir, filename)

            with open(filepath, "wb") as f:
                f.write(response.content)

            return filename

        except requests.RequestException as e:
            logger.warning(
                f"Network error downloading {accent} audio for {word} from Youdao: {e}"
            )
            return None
        except OSError as e:
            logger.warning(
                f"File system error downloading {accent} audio for {word} from Youdao: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error downloading {accent} audio for {word} from Youdao: {e}"
            )
            return None

    def download_word_audio(
        self, word: str, sources: list[str] | None = None
    ) -> AudioFiles:
        """Download both US and UK pronunciations for a word"""
        if settings.audio.offline:
            # In offline mode, do not perform any network calls.
            # Return empty AudioFiles so callers can proceed without audio.
            return AudioFiles()
        if sources is None:
            sources = ["google", "youdao"]

        audio_files = AudioFiles()

        for source in sources:
            try:
                if source == "google":
                    us_file = self.download_google_tts(word, "us")
                    uk_file = self.download_google_tts(word, "uk")
                elif source == "youdao":
                    us_file = self.download_youdao_tts(word, "us")
                    uk_file = self.download_youdao_tts(word, "uk")
                else:
                    continue

                if us_file and not audio_files.us_audio:
                    audio_files.us_audio = us_file
                if uk_file and not audio_files.uk_audio:
                    audio_files.uk_audio = uk_file

                # Stop if both files downloaded successfully
                if audio_files.has_us_audio and audio_files.has_uk_audio:
                    break

            except (requests.RequestException, OSError) as e:
                logger.warning(f"Failed to download from {source}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error downloading from {source}: {e}")
                continue

        return audio_files

    def check_audio_exists(self, word: str) -> dict[str, bool]:
        """Check if audio files already exist for a word.

        Delegates to CacheManager to avoid duplication.
        """
        try:
            from ..utils.cache_manager import CacheManager

            cm = CacheManager(audio_dir=self.audio_dir)
            status = cm.check_audio_cache(word)
            return {
                "us_exists": bool(status.get("us_exists")),
                "uk_exists": bool(status.get("uk_exists")),
            }
        except Exception:
            # Fallback local check
            patterns = get_audio_patterns(word)
            us_exists = any(
                os.path.exists(os.path.join(self.audio_dir, p))
                for p in patterns["us_patterns"]
            )
            uk_exists = any(
                os.path.exists(os.path.join(self.audio_dir, p))
                for p in patterns["uk_patterns"]
            )
            return {"us_exists": us_exists, "uk_exists": uk_exists}

    def batch_download(
        self, words: list[str], delay: float = 0.5
    ) -> dict[str, AudioFiles]:
        """Download audio for multiple words with rate limiting"""
        results: dict[str, AudioFiles] = {}

        if settings.audio.offline:
            # Skip any network; return empty AudioFiles for each word
            return {w: AudioFiles() for w in words}

        logger.info(f"Starting batch download for {len(words)} words...")

        for i, word in enumerate(words, 1):
            logger.info(f"({i}/{len(words)}) Downloading audio: {word}")

            # Check if audio already exists
            audio_status = self.check_audio_exists(word)
            if audio_status["us_exists"] and audio_status["uk_exists"]:
                logger.info("  Audio files already exist, skipping")
                patterns = get_audio_patterns(word)
                us_file = next(
                    (
                        f
                        for f in patterns["us_patterns"]
                        if os.path.exists(os.path.join(self.audio_dir, f))
                    ),
                    None,
                )
                uk_file = next(
                    (
                        f
                        for f in patterns["uk_patterns"]
                        if os.path.exists(os.path.join(self.audio_dir, f))
                    ),
                    None,
                )
                results[word] = AudioFiles(us_audio=us_file, uk_audio=uk_file)
                continue

            # Download missing audio files
            audio_files = self.download_word_audio(word)
            results[word] = audio_files

            if audio_files.has_us_audio and audio_files.has_uk_audio:
                logger.info("  Successfully downloaded both US and UK audio")
            elif audio_files.has_any_audio:
                logger.info("  Partially downloaded")
            else:
                logger.warning("  Download failed")

            # Rate limiting
            if i < len(words):
                time.sleep(delay)

        return results


# Convenience functions
def create_audio_directory() -> str:
    """Create and return audio directory path"""
    downloader = AudioDownloader()
    return downloader.audio_dir


def download_word_audio(word: str, audio_dir: str = "audio_files") -> AudioFiles:
    """Download word audio - convenience function"""
    downloader = AudioDownloader(audio_dir)
    return downloader.download_word_audio(word)
