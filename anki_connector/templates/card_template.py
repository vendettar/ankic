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
        """Define all fields for the vocabulary card"""
        fields = [
            {"name": "Word"},
            {"name": "US_Phonetic"},
            {"name": "UK_Phonetic"},
            {"name": "US_Audio"},
            {"name": "UK_Audio"},
            {"name": "vocab_WordForms"},
        ]

        # Add definition fields (vocab_Part1-vocab_Part25, vocab_Definition1-vocab_Definition25)
        for i in range(1, 26):
            fields.extend(
                [{"name": f"vocab_Part{i}"}, {"name": f"vocab_Definition{i}"}]
            )

        # Add explanation and additional content fields in correct order
        fields.extend(
            [
                {"name": "vocab_ShortExplanation"},
                {"name": "vocab_LongExplanation"},
                {"name": "Etymology"},
                {"name": "Tags"},
            ]
        )

        # Add MW-specific fields for structured data
        mw_fields = [
            # Collegiate dictionary fields
            {"name": "MW_Headword"},
            {"name": "MW_PartOfSpeech"},
            {"name": "MW_Stems"},
            {"name": "MW_Definitions"},
            {"name": "MW_Inflections"},
            {"name": "MW_Etymology"},
            {"name": "MW_FirstKnownUse"},
            {"name": "MW_Examples"},
            {"name": "MW_LearnerDefinitions"},
            # Thesaurus fields
            {"name": "MW_Synonyms"},
            {"name": "MW_Antonyms"},
        ]

        fields.extend(mw_fields)

        return fields
