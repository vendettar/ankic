"""Configuration management with Pydantic v2 settings style"""

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnkiSettings(BaseSettings):
    """Anki-related configuration settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    url: str = Field(
        default="http://localhost:8765", validation_alias=AliasChoices("ANKI_URL")
    )
    deck_name: str = Field(
        default="Ankic", validation_alias=AliasChoices("ANKI_DECK_NAME")
    )
    model_name: str = Field(
        default="Ankic", validation_alias=AliasChoices("ANKI_MODEL_NAME")
    )
    request_timeout: int = Field(
        default=10, validation_alias=AliasChoices("ANKI_REQUEST_TIMEOUT")
    )
    max_retries: int = Field(
        default=3, validation_alias=AliasChoices("ANKI_MAX_RETRIES")
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate Anki URL format"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Anki URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("request_timeout", "max_retries")
    @classmethod
    def validate_positive_integers(cls, v: int) -> int:
        """Validate positive integer values"""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class AudioSettings(BaseSettings):
    """Audio-related configuration settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    dir: Path = Field(
        default=Path("audio_files"), validation_alias=AliasChoices("ANKI_AUDIO_DIR")
    )
    delay: float = Field(default=1.0, validation_alias=AliasChoices("ANKI_AUDIO_DELAY"))
    max_concurrent_downloads: int = Field(
        default=3, validation_alias=AliasChoices("MAX_CONCURRENT_DOWNLOADS")
    )
    download_sources: list[str] = Field(
        default_factory=lambda: ["google", "youdao"],
        validation_alias=AliasChoices("AUDIO_SOURCES"),
    )
    enable_audio: bool = Field(
        default=True, validation_alias=AliasChoices("ENABLE_AUDIO")
    )
    offline: bool = Field(default=False, validation_alias=AliasChoices("AUDIO_OFFLINE"))

    @field_validator("dir")
    @classmethod
    def validate_audio_dir(cls, v: Path | str) -> Path:
        """Ensure audio directory exists"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("delay")
    @classmethod
    def validate_delay(cls, v: float) -> float:
        """Validate audio delay"""
        if v < 0:
            raise ValueError("Audio delay cannot be negative")
        return v

    @field_validator("max_concurrent_downloads")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        """Validate concurrent downloads limit"""
        if v <= 0 or v > 10:
            raise ValueError("Max concurrent downloads must be between 1 and 10")
        return v


class CacheSettings(BaseSettings):
    """Cache-related configuration settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    dir: Path = Field(
        default=Path(".cache"), validation_alias=AliasChoices("ANKI_CACHE_DIR")
    )
    ttl_days: int = Field(default=30, validation_alias=AliasChoices("CACHE_TTL_DAYS"))
    max_size_mb: int = Field(
        default=100, validation_alias=AliasChoices("CACHE_MAX_SIZE_MB")
    )
    enable_cache: bool = Field(
        default=True, validation_alias=AliasChoices("ENABLE_CACHE")
    )
    cleanup_on_start: bool = Field(
        default=True, validation_alias=AliasChoices("CACHE_CLEANUP_ON_START")
    )
    disable_disk: bool = Field(
        default=False, validation_alias=AliasChoices("CACHE_DISABLE_DISK")
    )

    @field_validator("dir")
    @classmethod
    def validate_cache_dir(cls, v: Path | str) -> Path:
        """Ensure cache directory exists"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("ttl_days", "max_size_mb")
    @classmethod
    def validate_positive_values(cls, v: int) -> int:
        """Validate positive values"""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class VocabularySettings(BaseSettings):
    """Vocabulary fetching configuration"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    base_url: str = Field(
        default="https://www.vocabulary.com/dictionary",
        validation_alias=AliasChoices("VOCAB_BASE_URL"),
    )
    request_timeout: int = Field(
        default=10, validation_alias=AliasChoices("VOCAB_REQUEST_TIMEOUT")
    )
    max_retries: int = Field(
        default=3, validation_alias=AliasChoices("VOCAB_MAX_RETRIES")
    )
    rate_limit_delay: float = Field(
        default=1.0, validation_alias=AliasChoices("VOCAB_RATE_LIMIT_DELAY")
    )
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        validation_alias=AliasChoices("VOCAB_USER_AGENT"),
    )
    cookie: str | None = Field(
        default=None, validation_alias=AliasChoices("VOCAB_COOKIE")
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("request_timeout", "max_retries")
    @classmethod
    def validate_positive_integers(cls, v: int) -> int:
        """Validate positive integer values"""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @field_validator("rate_limit_delay")
    @classmethod
    def validate_rate_limit(cls, v: float) -> float:
        """Validate rate limit delay"""
        if v < 0:
            raise ValueError("Rate limit delay cannot be negative")
        return v


class LoggingSettings(BaseSettings):
    """Logging configuration"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    file: Path | None = Field(default=None, validation_alias=AliasChoices("LOG_FILE"))
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        validation_alias=AliasChoices("LOG_FORMAT"),
    )
    max_size_mb: int = Field(
        default=10, validation_alias=AliasChoices("LOG_MAX_SIZE_MB")
    )
    backup_count: int = Field(
        default=5, validation_alias=AliasChoices("LOG_BACKUP_COUNT")
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("max_size_mb", "backup_count")
    @classmethod
    def validate_positive_integers(cls, v: int) -> int:
        """Validate positive integer values"""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class MerriamWebsterSettings(BaseSettings):
    """Merriam‑Webster API settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    base_url: str = Field(
        default="https://dictionaryapi.com/api/v3/references",
        validation_alias=AliasChoices("MW_BASE_URL"),
    )
    collegiate_key: str | None = Field(
        default=None, validation_alias=AliasChoices("MW_COLLEGIATE_KEY")
    )
    thesaurus_key: str | None = Field(
        default=None, validation_alias=AliasChoices("MW_THESAURUS_KEY")
    )
    enable: bool = Field(default=True, validation_alias=AliasChoices("MW_ENABLE"))
    timeout: int = Field(default=8, validation_alias=AliasChoices("MW_TIMEOUT"))
    official_website_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("MW_OFFICIAL_WEBSITE_MODE"),
        description="Filter entries to match official Merriam-Webster website display (main entries only)",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("MW base URL must start with http:// or https://")
        return v.rstrip("/")


class AppSettings(BaseSettings):
    """Main application settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_nested_delimiter="__", case_sensitive=False, extra="ignore"
    )

    anki: AnkiSettings = Field(default_factory=AnkiSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    vocabulary: VocabularySettings = Field(default_factory=VocabularySettings)
    mw: MerriamWebsterSettings = Field(default_factory=MerriamWebsterSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # Global settings
    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG"))
    verbose: bool = Field(default=False, validation_alias=AliasChoices("VERBOSE"))
    max_workers: int = Field(default=5, validation_alias=AliasChoices("MAX_WORKERS"))
    fast_mode: bool = Field(
        default=False, validation_alias=AliasChoices("ANKIC_FAST", "FAST")
    )

    @field_validator("max_workers")
    @classmethod
    def validate_max_workers(cls, v: int) -> int:
        """Validate max workers"""
        if v <= 0 or v > 20:
            raise ValueError("Max workers must be between 1 and 20")
        return v

    def get_all_paths(self) -> list[Path]:
        """Get all configured paths"""
        paths = []
        if hasattr(self.audio, "dir"):
            paths.append(self.audio.dir)
        if hasattr(self.cache, "dir"):
            paths.append(self.cache.dir)
        if self.logging.file:
            paths.append(self.logging.file.parent)
        return paths

    def create_directories(self) -> None:
        """Create all necessary directories"""
        for path in self.get_all_paths():
            path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = AppSettings()
