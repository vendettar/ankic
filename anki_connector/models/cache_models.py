"""Pydantic models for cache-related data structures"""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CacheConfig(BaseModel):
    """Configuration for cache behavior"""

    ttl_days: int = Field(default=30, description="Time to live in days")
    max_size_mb: int = Field(default=100, description="Maximum cache size in MB")
    cleanup_interval_hours: int = Field(
        default=24, description="Cleanup interval in hours"
    )
    enable_compression: bool = Field(
        default=False, description="Enable data compression"
    )

    @field_validator("ttl_days")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL value"""
        if v <= 0:
            raise ValueError("TTL must be positive")
        return v

    @field_validator("max_size_mb")
    @classmethod
    def validate_max_size(cls, v: int) -> int:
        """Validate max size"""
        if v <= 0:
            raise ValueError("Max size must be positive")
        return v

    @field_validator("cleanup_interval_hours")
    @classmethod
    def validate_cleanup_interval(cls, v: int) -> int:
        """Validate cleanup interval"""
        if v <= 0:
            raise ValueError("Cleanup interval must be positive")
        return v


class CacheEntry(BaseModel):
    """Model for cache entry"""

    key: str = Field(description="Cache key")
    data: Any = Field(description="Cached data")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    access_count: int = Field(default=0, description="Access count")
    last_accessed: datetime = Field(
        default_factory=datetime.now, description="Last access time"
    )
    expires_at: datetime | None = Field(None, description="Expiration time")

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validate cache key"""
        if not v or not v.strip():
            raise ValueError("Cache key cannot be empty")
        return v.strip()

    @field_validator("access_count")
    @classmethod
    def validate_access_count(cls, v: int) -> int:
        """Validate access count"""
        if v < 0:
            raise ValueError("Access count cannot be negative")
        return v

    def is_expired(self, ttl_days: int = 30) -> bool:
        """Check if the cache entry is expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at

        # Fall back to TTL-based expiration
        expiry_time = self.timestamp + timedelta(days=ttl_days)
        return datetime.now() > expiry_time

    def touch(self) -> None:
        """Update access information"""
        self.access_count += 1
        self.last_accessed = datetime.now()

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CacheStats(BaseModel):
    """Model for cache statistics"""

    total_entries: int = Field(description="Total number of entries")
    valid_entries: int = Field(description="Number of valid entries")
    expired_entries: int = Field(description="Number of expired entries")
    cache_size_mb: float = Field(description="Cache size in MB")
    hit_rate: float = Field(description="Cache hit rate percentage")
    last_cleanup: datetime | None = Field(None, description="Last cleanup time")

    @field_validator("hit_rate")
    @classmethod
    def validate_hit_rate(cls, v: float) -> float:
        """Validate hit rate percentage"""
        if not 0 <= v <= 100:
            raise ValueError("Hit rate must be between 0 and 100")
        return v


class CacheMetadata(BaseModel):
    """Model for cache metadata"""

    version: str = Field(description="Cache format version")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Cache creation time"
    )
    last_updated: datetime = Field(
        default_factory=datetime.now, description="Last update time"
    )
    config: CacheConfig = Field(
        default_factory=CacheConfig, description="Cache configuration"
    )
    stats: CacheStats = Field(description="Cache statistics")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format"""
        if not v or not v.strip():
            raise ValueError("Version cannot be empty")
        return v.strip()


class AudioCacheEntry(BaseModel):
    """Model for audio file cache entry"""

    word: str = Field(description="Word for the audio")
    us_file: str | None = Field(None, description="US pronunciation filename")
    uk_file: str | None = Field(None, description="UK pronunciation filename")
    file_sizes: dict[str, int] = Field(default={}, description="File sizes in bytes")
    download_timestamp: datetime = Field(
        default_factory=datetime.now, description="Download time"
    )
    source: str | None = Field(None, description="Audio source")

    @field_validator("word")
    @classmethod
    def validate_word(cls, v: str) -> str:
        """Validate word"""
        if not v or not v.strip():
            raise ValueError("Word cannot be empty")
        return v.strip().lower()

    def get_total_size(self) -> int:
        """Get total size of audio files"""
        return sum(self.file_sizes.values())

    def has_complete_audio(self) -> bool:
        """Check if both US and UK audio are available"""
        return bool(self.us_file and self.uk_file)
