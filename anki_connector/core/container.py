"""Dependency injection container for managing service dependencies"""

from collections.abc import Callable
from typing import Any, TypeVar

from .interfaces import (
    AnkiClientInterface,
    AudioDownloaderInterface,
    CacheManagerInterface,
    ContentEnricherInterface,
    TextProcessorInterface,
    VocabularyFetcherInterface,
)

T = TypeVar("T")


class DIContainer:
    """Simple dependency injection container"""

    def __init__(self) -> None:
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable[[], Any]] = {}
        self._singletons: dict[type, Any] = {}

    def register_instance(self, interface: type[Any], instance: Any) -> None:
        """Register a specific instance for an interface"""
        self._services[interface] = instance

    def register_factory(
        self, interface: type[Any], factory: Callable[[], Any]
    ) -> None:
        """Register a factory function for an interface"""
        self._factories[interface] = factory

    def register_singleton(
        self, interface: type[Any], factory: Callable[[], Any]
    ) -> None:
        """Register a singleton factory for an interface"""
        self._factories[interface] = factory
        # Mark as singleton (value set on first access)
        if interface not in self._singletons:
            self._singletons[interface] = None

    def get(self, interface: type[Any]) -> Any | None:
        """Get an instance of the requested interface"""
        # Check if we have a direct instance
        if interface in self._services:
            return self._services[interface]

        # Check if it's a singleton that's already been created
        if interface in self._singletons and self._singletons[interface] is not None:
            return self._singletons[interface]

        # Check if we have a factory
        if interface in self._factories:
            instance = self._factories[interface]()

            # If it's a singleton, store the instance
            if interface in self._singletons:
                self._singletons[interface] = instance

            return instance

        return None

    def has(self, interface: type[Any]) -> bool:
        """Check if the container can provide an instance of the interface"""
        return (
            interface in self._services
            or interface in self._factories
            or (
                interface in self._singletons
                and self._singletons[interface] is not None
            )
        )

    def clear(self) -> None:
        """Clear all registrations"""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


class ServiceLocator:
    """Global service locator for accessing the DI container"""

    _container: DIContainer | None = None

    @classmethod
    def set_container(cls, container: DIContainer) -> None:
        """Set the global container instance"""
        cls._container = container

    @classmethod
    def get_container(cls) -> DIContainer:
        """Get the global container instance"""
        if cls._container is None:
            cls._container = DIContainer()
        return cls._container

    @classmethod
    def get(cls, interface: type[T]) -> T | None:
        """Convenience method to get service from global container"""
        return cls.get_container().get(interface)


def setup_default_container() -> DIContainer:
    """Setup container with default implementations"""
    from ..enrichment.mw_enricher import MerriamWebsterEnricher
    from ..utils.cache_manager import CacheManager
    from .anki_client import AnkiClient
    from .audio_downloader import AudioDownloader
    from .text_processor import TextProcessor
    from .vocabulary_fetcher import VocabularyFetcher

    container = DIContainer()

    # Register factories for default implementations
    container.register_singleton(
        VocabularyFetcherInterface, lambda: VocabularyFetcher()
    )
    container.register_singleton(AudioDownloaderInterface, lambda: AudioDownloader())
    container.register_singleton(AnkiClientInterface, lambda: AnkiClient())
    container.register_singleton(TextProcessorInterface, lambda: TextProcessor())
    container.register_singleton(CacheManagerInterface, lambda: CacheManager())
    # Optional content enrichers
    container.register_singleton(
        ContentEnricherInterface, lambda: MerriamWebsterEnricher()
    )

    return container
