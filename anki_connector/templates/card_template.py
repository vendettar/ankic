"""Anki card templates for vocabulary cards (fields + Jinja visuals).

Default visuals: vapor theme (with base as shared includes).
"""

from typing import Any

from .loader import load_card_visuals


class VocabularyCardTemplate:
    """Template for vocabulary cards in Anki.

    - Fields are defined here
    - Visuals (front/back/css) are loaded from Jinja templates
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    def _load_default_visuals(self) -> tuple[str, str, str]:
        # Default to packaged 'vapor' theme; theme loader falls back to base/assets as needed
        front, back, css = load_card_visuals("vapor")  # type: ignore
        return front, back, css

    def create_card_type(self) -> dict[str, Any]:
        """Create the complete card type configuration using default theme visuals"""
        front, back, css = self._load_default_visuals()
        return {
            "modelName": self.model_name,
            "fields": self._get_fields(),
            "css": css,
            "front_template": front,
            "back_template": back,
        }

    def _get_fields(self) -> list[dict[str, str]]:
        """Define all fields for the vocabulary card in display order"""
        fields = []

        # 1. Basic word info fields (as shown in word-section)
        basic_fields = [
            {"name": "Word"},
            {"name": "USPhonetic"},
            {"name": "UKPhonetic"},
            {"name": "USAudio"},
            {"name": "UKAudio"},
        ]
        fields.extend(basic_fields)

        # 2. Vocabulary-related fields
        vocab_fields = []

        # Vocabulary structured entries (VocabEntry1-VocabEntry25)
        # Each entry contains part of speech + definition in one field (like MW format)
        for i in range(1, 26):
            vocab_fields.append({"name": f"VocabEntry{i}"})

        # Vocabulary additional fields
        vocab_fields.extend(
            [
                {"name": "VocabWordForms"},
                {"name": "VocabShortExplanation"},
                {"name": "VocabLongExplanation"},
            ]
        )

        fields.extend(vocab_fields)

        # 3. MW (Merriam-Webster) fields (in order of appearance in template)
        mw_fields = [
            # MW basic info
            {"name": "MWStems"},
        ]

        # MW structured entries (MWStructuredEntry1-MWStructuredEntry25)
        for i in range(1, 26):
            mw_fields.append({"name": f"MWStructuredEntry{i}"})

        # MW additional content
        mw_fields.extend(
            [
                {"name": "MWPronunciation"},  # IPA pronunciations
                {"name": "MWWordInflections"},  # Word forms (ins field)
                {"name": "MWLearnerDefinitions"},
                {"name": "MWExamples"},
                {"name": "MWSynonyms"},
                {"name": "MWAntonyms"},
                {"name": "MWCollegiateSynonyms"},  # Detailed synonyms explanation
                {"name": "MWEtymology"},
            ]
        )

        fields.extend(mw_fields)

        # 4. General fields (Etymology and Tags)
        general_fields = [
            {"name": "Etymology"},
            {"name": "Tags"},
        ]
        fields.extend(general_fields)

        return fields
