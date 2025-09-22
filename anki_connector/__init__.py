"""
Modern Anki Vocabulary Tool - Vcabulary card generator for Anki
"""

__version__ = "1.0.0"
__author__ = "Nullius"
__description__ = "Modern vocabulary importer for Anki with DI and caching"

# Export main factory function for easy access
from .core.factory import create_vocabulary_processor

__all__ = ["create_vocabulary_processor"]
