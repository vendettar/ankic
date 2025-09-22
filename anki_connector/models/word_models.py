"""Audio file models for word information"""

from dataclasses import dataclass


@dataclass
class AudioFiles:
    """Audio file information for a word"""

    us_audio: str | None = None
    uk_audio: str | None = None

    @property
    def has_us_audio(self) -> bool:
        """Check if US audio is available"""
        return self.us_audio is not None

    @property
    def has_uk_audio(self) -> bool:
        """Check if UK audio is available"""
        return self.uk_audio is not None

    @property
    def has_any_audio(self) -> bool:
        """Check if any audio is available"""
        return self.has_us_audio or self.has_uk_audio
