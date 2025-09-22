"""Pydantic models for Anki-related data structures"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnkiModel(BaseModel):
    """Model for Anki note type/model"""

    name: str = Field(description="Model name")
    fields: list[str] = Field(description="Field names")
    css: str = Field(description="CSS styling")
    templates: list[dict[str, str]] = Field(description="Card templates")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate model name"""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: list[str]) -> list[str]:
        """Validate field list"""
        if not v:
            raise ValueError("Model must have at least one field")
        return [field.strip() for field in v if field and field.strip()]


class AnkiDeck(BaseModel):
    """Model for Anki deck"""

    name: str = Field(description="Deck name")
    description: str | None = Field(None, description="Deck description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate deck name"""
        if not v or not v.strip():
            raise ValueError("Deck name cannot be empty")
        return v.strip()


class AnkiNote(BaseModel):
    """Model for Anki note"""

    deck_name: str = Field(description="Target deck name")
    model_name: str = Field(description="Note type/model name")
    fields: dict[str, str] = Field(description="Field values")
    tags: list[str] = Field(default=[], description="Note tags")
    note_id: int | None = Field(None, description="Note ID if it exists")

    @field_validator("deck_name", "model_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        """Validate deck and model names"""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: dict[str, Any]) -> dict[str, str]:
        """Validate field data"""
        if not v:
            raise ValueError("Note must have at least one field")
        # Clean field values
        return {k: str(val).strip() if val else "" for k, val in v.items()}

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Clean and validate tags"""
        return [tag.strip() for tag in v if tag and tag.strip()]


class AnkiCardTemplate(BaseModel):
    """Model for Anki card template"""

    name: str = Field(description="Template name")
    front: str = Field(description="Front template HTML")
    back: str = Field(description="Back template HTML")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate template name"""
        if not v or not v.strip():
            raise ValueError("Template name cannot be empty")
        return v.strip()

    @field_validator("front", "back")
    @classmethod
    def validate_templates(cls, v: str) -> str:
        """Validate template content"""
        if not v:
            return ""
        return v.strip()


class AnkiMediaFile(BaseModel):
    """Model for Anki media files"""

    filename: str = Field(description="Media filename")
    data: bytes = Field(description="File content")
    content_type: str | None = Field(None, description="MIME type")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename"""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        return v.strip()

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow bytes type


class AnkiOperationResult(BaseModel):
    """Model for Anki operation results"""

    success: bool = Field(description="Operation success status")
    result: Any | None = Field(None, description="Operation result data")
    error: str | None = Field(None, description="Error message if failed")
    operation: str = Field(description="Operation type")

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate operation name"""
        if not v or not v.strip():
            raise ValueError("Operation name cannot be empty")
        return v.strip()

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Any type for result
