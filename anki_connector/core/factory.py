"""Factory functions for creating configured instances"""

from typing import cast

from .container import DIContainer, setup_default_container
from .interfaces import (
    AnkiClientInterface,
    AudioDownloaderInterface,
    CacheManagerInterface,
    ContentEnricherInterface,
    TextProcessorInterface,
    VocabularyFetcherInterface,
)
from .vocabulary_processor import VocabularyProcessor


class VocabularyProcessorFactory:
    """Factory for creating VocabularyProcessor instances"""

    @staticmethod
    def create_default() -> VocabularyProcessor:
        """Create processor with default dependencies"""
        container = setup_default_container()
        return VocabularyProcessorFactory.create_from_container(container)

    @staticmethod
    def create_from_container(
        container: DIContainer,
        deck_name: str | None = None,
        template: str | None = None,
    ) -> VocabularyProcessor:
        """Create processor from DI container"""

        # Get dependencies from container
        vocabulary_fetcher = cast(
            VocabularyFetcherInterface, container.get(VocabularyFetcherInterface)
        )
        audio_downloader = cast(
            AudioDownloaderInterface, container.get(AudioDownloaderInterface)
        )
        anki_client = cast(AnkiClientInterface, container.get(AnkiClientInterface))
        cache_manager = cast(
            CacheManagerInterface, container.get(CacheManagerInterface)
        )
        text_processor = cast(
            TextProcessorInterface, container.get(TextProcessorInterface)
        )
        # Enrichers are optional; container returns single instance by interface.
        enricher = container.get(ContentEnricherInterface)
        enrichers = [enricher] if enricher else []

        # Validate all dependencies are available
        if not all(
            [
                vocabulary_fetcher,
                audio_downloader,
                anki_client,
                cache_manager,
                text_processor,
            ]
        ):
            raise RuntimeError(
                "Some required dependencies are not registered in the container"
            )

        return VocabularyProcessor(
            vocabulary_fetcher=vocabulary_fetcher,
            audio_downloader=audio_downloader,
            anki_client=anki_client,
            cache_manager=cache_manager,
            text_processor=text_processor,
            deck_name=deck_name,
            template_spec=template,
            enrichers=enrichers,
        )

    @staticmethod
    def create_custom(
        vocabulary_fetcher: VocabularyFetcherInterface,
        audio_downloader: AudioDownloaderInterface,
        anki_client: AnkiClientInterface,
        cache_manager: CacheManagerInterface,
        text_processor: TextProcessorInterface,
        deck_name: str | None = None,
        template: str | None = None,
    ) -> VocabularyProcessor:
        """Create processor with custom dependencies"""

        return VocabularyProcessor(
            vocabulary_fetcher=vocabulary_fetcher,
            audio_downloader=audio_downloader,
            anki_client=anki_client,
            cache_manager=cache_manager,
            text_processor=text_processor,
            deck_name=deck_name,
            template_spec=template,
        )


def create_vocabulary_processor(
    deck_name: str | None = None,
    template: str | None = None,
    container: DIContainer | None = None,
) -> VocabularyProcessor:
    """Convenience function to create a vocabulary processor"""

    if container:
        return VocabularyProcessorFactory.create_from_container(
            container, deck_name, template
        )
    else:
        return VocabularyProcessorFactory.create_from_container(
            setup_default_container(), deck_name, template
        )


def setup_test_container() -> DIContainer:
    """Setup container with test/mock implementations"""
    # This would be implemented with mock objects for testing
    # For now, return default container
    return setup_default_container()
