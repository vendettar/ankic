"""Pydantic models for word information and vocabulary data"""

import re

from pydantic import BaseModel, Field, field_validator


class WordDefinition(BaseModel):
    """Model for a single word definition"""

    part_of_speech: str = Field(description="Part of speech (noun, verb, etc.)")
    definition: str = Field(description="Definition text")
    examples: list[str] = Field(default=[], description="Usage examples")
    synonyms: list[str] = Field(default=[], description="Synonyms")
    antonyms: list[str] = Field(default=[], description="Antonyms")

    @field_validator("part_of_speech")
    @classmethod
    def validate_part_of_speech(cls, v: str) -> str:
        """Normalize part of speech"""
        if not v:
            return ""
        return v.strip().lower()

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: str) -> str:
        """Ensure definition is not empty"""
        if not v or not v.strip():
            raise ValueError("Definition cannot be empty")
        return v.strip()

    @field_validator("examples")
    @classmethod
    def validate_examples(cls, v: list[str]) -> list[str]:
        """Clean and validate examples"""
        return [ex.strip() for ex in v if ex and ex.strip()]

    @field_validator("synonyms", "antonyms")
    @classmethod
    def validate_word_lists(cls, v: list[str]) -> list[str]:
        """Clean and validate synonym/antonym lists"""
        return [word.strip() for word in v if word and word.strip()]


class Phonetics(BaseModel):
    """Model for phonetic information"""

    us: str | None = Field(None, description="US pronunciation")
    uk: str | None = Field(None, description="UK pronunciation")

    @field_validator("us", "uk")
    @classmethod
    def validate_phonetic(cls, v: str | None) -> str | None:
        """Validate phonetic notation format"""
        if not v:
            return None

        v = v.strip()
        # Ensure phonetics are wrapped in forward slashes
        if v and not (v.startswith("/") and v.endswith("/")):
            v = f"/{v}/"

        return v


class WordForms(BaseModel):
    """Model for word forms and variations"""

    forms: list[str] = Field(default=[], description="Alternative word forms")

    @field_validator("forms")
    @classmethod
    def validate_forms(cls, v: list[str]) -> list[str]:
        """Clean and validate word forms"""
        cleaned_forms = []
        for form in v:
            if form and isinstance(form, str):
                clean_form = form.strip()
                if clean_form and clean_form not in cleaned_forms:
                    cleaned_forms.append(clean_form)
        return cleaned_forms


class WordInfo(BaseModel):
    """Main model for comprehensive word information"""

    word: str = Field(description="The word itself")
    phonetics: Phonetics = Field(
        default_factory=lambda: Phonetics(us=None, uk=None),
        description="Phonetic information",
    )
    definitions: list[WordDefinition] = Field(
        default=[], description="Word definitions"
    )
    word_forms: WordForms = Field(
        default_factory=lambda: WordForms(forms=[]),
        description="Word forms and variations",
    )
    short_explanation: str | None = Field(None, description="Brief explanation")
    long_explanation: str | None = Field(None, description="Detailed explanation")
    etymology: str | None = Field(None, description="Etymology information")
    source: str | None = Field(None, description="Data source")

    @field_validator("word")
    @classmethod
    def validate_word(cls, v: str) -> str:
        """Validate and normalize the word"""
        if not v or not v.strip():
            raise ValueError("Word cannot be empty")

        word = v.strip().lower()

        # Check basic word format
        if not re.match(r"^[a-zA-Z](?:[a-zA-Z\s\-']*[a-zA-Z])?$", word):
            raise ValueError(f"Invalid word format: {word}")

        # Check length
        if len(word) > 50:
            raise ValueError(f"Word too long: {word}")

        return word

    @field_validator("definitions")
    @classmethod
    def validate_definitions(cls, v: list[WordDefinition]) -> list[WordDefinition]:
        """Ensure at least one definition exists for valid words"""
        if not v:
            return v  # Allow empty for now, can be filled later
        return v

    @field_validator("short_explanation", "long_explanation", "etymology")
    @classmethod
    def validate_text_fields(cls, v: str | None) -> str | None:
        """Clean text fields"""
        if not v:
            return None
        return v.strip()
