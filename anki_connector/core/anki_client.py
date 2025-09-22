"""Anki integration client using AnkiConnect API"""

import base64
import os
from typing import Any, cast

import requests  # type: ignore[import-untyped]
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util import Retry

from ..config.settings import settings
from ..models.word_models import AudioFiles
from .constants import get_audio_patterns
from .interfaces import AnkiClientInterface


class AnkiClient(AnkiClientInterface):
    """Client for communicating with Anki via AnkiConnect"""

    def __init__(self, url: str | None = None, timeout: int | None = None):
        """Initialize client.

        Args:
            url: AnkiConnect endpoint. Defaults to Config value.
            timeout: Request timeout seconds. Defaults to Config value.
        """
        self.url = url or settings.anki.url
        self.timeout = int(
            timeout if timeout is not None else settings.anki.request_timeout
        )
        self.version = 6
        self.session = requests.Session()
        self._configure_retries()

    def _configure_retries(self) -> None:
        retry = Retry(
            total=3,
            backoff_factor=0.2,
            status_forcelist=(502, 503, 504),
            allowed_methods=("POST", "GET"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def invoke(self, action: str, **params: Any) -> dict[str, Any]:
        """Send request to AnkiConnect"""
        payload = {"action": action, "version": self.version, "params": params}
        try:
            response = self.session.post(self.url, json=payload, timeout=self.timeout)
            return cast(dict[str, Any], response.json())
        except requests.RequestException as e:
            return {"result": None, "error": str(e)}

    def create_deck(self, deck_name: str) -> bool:
        """Create deck if it doesn't exist"""
        existing_decks = self.get_deck_names()
        if deck_name in existing_decks:
            return True

        response = self.invoke("createDeck", deck=deck_name)
        return response.get("error") is None

    def get_deck_names(self) -> list[str]:
        """Get list of all deck names"""
        response = self.invoke("deckNames")
        res = response.get("result")
        if isinstance(res, list):
            return cast(list[str], res)
        return []

    def create_model(
        self,
        model_name: str,
        fields: list[str],
        css: str,
        templates: list[dict[str, str]],
    ) -> bool:
        """Create card model/note type"""
        model_data = {
            "modelName": model_name,
            "inOrderFields": fields,
            "css": css,
            "cardTemplates": templates,
        }
        response = self.invoke("createModel", **model_data)
        return response.get("error") is None

    def update_model_templates(
        self,
        model_name: str,
        css: str,
        templates: list[dict[str, str]],
        card_name: str = "AnkicCard",
    ) -> bool:
        """Update model templates and styling in Anki if model already exists."""
        # Update templates
        tmpl_map = {
            card_name: {"Front": templates[0]["Front"], "Back": templates[0]["Back"]}
        }
        r1 = self.invoke(
            "updateModelTemplates", model={"name": model_name, "templates": tmpl_map}
        )
        # Update CSS
        r2 = self.invoke("updateModelStyling", model={"name": model_name, "css": css})
        return (r1.get("error") is None) and (r2.get("error") is None)

    def get_model_names(self) -> list[str]:
        """Get list of all model names"""
        response = self.invoke("modelNames")
        res = response.get("result")
        if isinstance(res, list):
            return cast(list[str], res)
        return []

    def get_model_field_names(self, model_name: str) -> list[str]:
        """Get field names for a model"""
        response = self.invoke("modelFieldNames", modelName=model_name)
        res = response.get("result", [])
        return cast(list[str], res)

    def add_model_field(self, model_name: str, field_name: str) -> bool:
        """Add a field to a model if supported by AnkiConnect"""
        response = self.invoke(
            "modelFieldAdd", modelName=model_name, fieldName=field_name
        )
        return response.get("error") is None

    def ensure_model_fields(self, model_name: str, required_fields: list[str]) -> None:
        """Ensure that all required fields exist in the model (add missing ones)."""
        try:
            existing = set(self.get_model_field_names(model_name) or [])
            for fname in required_fields:
                if fname not in existing:
                    self.add_model_field(model_name, fname)
        except Exception as e:
            from ..logging_config import get_logger

            logger = get_logger(__name__)
            logger.debug(f"Failed to ensure model fields for {model_name}: {e}")

    def add_note(
        self,
        deck_name: str,
        model_name: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
    ) -> int | None:
        """Add a new note to Anki"""
        note_data = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            # Restrict duplicate check to the target deck to avoid false negatives
            "options": {
                "allowDuplicate": False,
                "duplicateScope": "deck",
                "duplicateScopeOptions": {
                    "deckName": deck_name,
                    "checkChildren": True,
                    "checkAllModels": False,
                },
            },
            "tags": tags or [],
        }
        response = self.invoke("addNote", note=note_data)
        if response.get("error"):
            from ..logging_config import get_logger

            get_logger(__name__).warning(f"Anki addNote error: {response.get('error')}")
        return response.get("result")

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> bool:
        """Update existing note fields"""
        response = self.invoke(
            "updateNoteFields", note={"id": note_id, "fields": fields}
        )
        return response.get("error") is None

    def find_notes(self, query: str) -> list[int]:
        """Find notes matching query"""
        response = self.invoke("findNotes", query=query)
        res = response.get("result", [])
        return cast(list[int], res)

    def store_media_file(
        self, file_path: str, filename: str | None = None
    ) -> str | None:
        """Upload media file to Anki's media collection"""
        if not os.path.exists(file_path):
            return None

        if filename is None:
            filename = os.path.basename(file_path)

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            encoded_data = base64.b64encode(file_data).decode("utf-8")
            response = self.invoke(
                "storeMediaFile", filename=filename, data=encoded_data
            )

            return filename if response.get("error") is None else None
        except Exception as e:
            from ..logging_config import get_logger

            logger = get_logger(__name__)
            logger.debug(f"Failed to store media file {filename}: {e}")
            return None

    def store_word_audio_files(
        self, word: str, audio_dir: str = "audio_files"
    ) -> AudioFiles:
        """Upload word's US and UK audio files to Anki media library"""
        audio_files = AudioFiles()

        patterns = get_audio_patterns(word)

        # Upload US audio
        for pattern in patterns["us_patterns"]:
            file_path = os.path.join(audio_dir, pattern)
            if os.path.exists(file_path):
                uploaded = self.store_media_file(file_path, f"{word}_us.mp3")
                if uploaded:
                    audio_files.us_audio = uploaded
                    break

        # Upload UK audio
        for pattern in patterns["uk_patterns"]:
            file_path = os.path.join(audio_dir, pattern)
            if os.path.exists(file_path):
                uploaded = self.store_media_file(file_path, f"{word}_uk.mp3")
                if uploaded:
                    audio_files.uk_audio = uploaded
                    break

        return audio_files
