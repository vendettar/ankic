"""Merriam-Webster content enricher.

Fetches data from Merriam-Webster Collegiate and Thesaurus APIs
and composes a single HTML block in field `MW_Content`.

Design:
- Respect settings.mw (base_url, keys, enable, timeout)
- Best-effort parsing; robust to missing keys
- No network if audio offline fast-mode? We still allow network here;
  callers can decide to disable by not registering the enricher or
  by leaving keys unset. Errors are swallowed with logs.
"""

from __future__ import annotations

from typing import Any

import requests  # type: ignore[import-untyped]

from ..config.settings import settings
from ..core.interfaces import ContentEnricherInterface
from ..logging_config import get_logger

logger = get_logger(__name__)


class MerriamWebsterEnricher(ContentEnricherInterface):
    def __init__(self) -> None:
        self.base = settings.mw.base_url.rstrip("/")
        self.timeout = int(settings.mw.timeout)

    def enrich(self, word: str, info: Any | None) -> dict[str, str]:
        if not settings.mw.enable:
            return {}
        # Enrich only when at least one API key is configured
        if not any([settings.mw.collegiate_key, settings.mw.thesaurus_key]):
            return {}

        mw_data: dict[str, Any] = {}
        try:
            collegiate_data = self._fetch_collegiate_data(word)
            if collegiate_data:
                mw_data["collegiate"] = collegiate_data
        except Exception as e:
            logger.debug(f"MW Collegiate fetch failed for {word}: {e}")

        try:
            thesaurus_data = self._fetch_thesaurus_data(word)
            if thesaurus_data:
                mw_data["thesaurus"] = thesaurus_data
        except Exception as e:
            logger.debug(f"MW Thesaurus fetch failed for {word}: {e}")

        if not mw_data:
            return {}

        # Convert structured MW data to individual Anki fields
        return self._extract_mw_fields(mw_data)

    def _fetch_json(self, ref: str, word: str, key: str | None) -> Any:
        # Only call API when a key is provided for this dataset
        if not key:
            return None
        url = f"{self.base}/{ref}/json/{word}?key={key}"
        r = requests.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _fetch_collegiate_data(self, word: str) -> dict[str, Any] | None:
        data = self._fetch_json("collegiate", word, settings.mw.collegiate_key)
        if not data or not isinstance(data, list):
            return None
        entries: list[dict[str, Any]] = []
        for entry in data[:3]:
            entry_data: dict[str, Any] = {}

            # Extract headword and part of speech
            headword = (entry.get("hwi") or {}).get("hw") or ""
            fl = entry.get("fl") or ""
            if headword:
                entry_data["headword"] = headword
            if fl:
                entry_data["part_of_speech"] = fl

            # Extract stems
            stems = entry.get("meta", {}).get("stems") or []
            if stems:
                entry_data["stems"] = stems[:10]

            # Extract definitions from shortdef
            definitions = []
            for dtext in (entry.get("shortdef") or [])[:6]:
                txt = self._mw_markup_to_text(dtext)
                if txt:
                    definitions.append(txt)
            if definitions:
                entry_data["definitions"] = definitions

            # Extract inflections (uros)
            uros = entry.get("uros") or []
            inflections = []
            for u in uros[:6]:
                ure = u.get("ure") or ""
                ufl = u.get("fl") or ""
                if ure:
                    inflection = {"form": ure}
                    if ufl:
                        inflection["type"] = ufl
                    inflections.append(inflection)
            if inflections:
                entry_data["inflections"] = inflections

            # Extract etymology
            et_list = entry.get("et") or []
            et_texts = []
            for et in et_list[:3]:
                if isinstance(et, list) and et and et[0] == "text":
                    et_texts.append(self._mw_markup_to_text(et[1]))
                elif isinstance(et, dict) and "text" in et:
                    et_texts.append(self._mw_markup_to_text(et.get("text", "")))
            if et_texts:
                entry_data["etymology"] = et_texts

            # Extract first known use date
            date = entry.get("date")
            if date:
                entry_data["first_known_use"] = self._mw_markup_to_text(date)

            # Extract examples
            suppl = entry.get("suppl") or {}
            examples = []
            for ex in (suppl.get("examples") or [])[:4]:
                t = ex.get("t")
                if t:
                    examples.append(self._mw_markup_to_text(t))
            if examples:
                entry_data["examples"] = examples
            ldq = suppl.get("ldq") or {}
            ld_defs: list[str] = []
            for d in (ldq.get("def") or [])[:2]:
                for sseq in d.get("sseq", [])[:3]:
                    try:
                        sense = sseq[0][1]
                        dt = sense.get("dt", [])
                        for dt_item in dt:
                            if dt_item and dt_item[0] == "text":
                                ld_defs.append(self._mw_markup_to_text(dt_item[1]))
                                break
                    except Exception:
                        continue
            if ld_defs:
                entry_data["learner_definitions"] = ld_defs

            # Add entry only if it has meaningful content
            if entry_data:
                entries.append(entry_data)

        return {"entries": entries} if entries else None

    def _fetch_thesaurus_data(self, word: str) -> dict[str, Any] | None:
        data = self._fetch_json("thesaurus", word, settings.mw.thesaurus_key)
        if not data or not isinstance(data, list):
            return None
        synonyms: list[str] = []
        antonyms: list[str] = []
        for entry in data:
            meta = entry.get("meta") or {}
            for group in meta.get("syns", [])[:4]:
                for s in group[:6]:
                    synonyms.append(s)
            for group in meta.get("ants", [])[:4]:
                for a in group[:6]:
                    antonyms.append(a)
            # From sense lists (syn_list, rel_list, ant_list, near_list)
            for d in entry.get("def", []) or []:
                for sseq in d.get("sseq", [])[:3]:
                    try:
                        sense = sseq[0][1]
                        for key, target in (
                            ("syn_list", synonyms),
                            ("rel_list", synonyms),
                            ("ant_list", antonyms),
                            ("near_list", synonyms),
                        ):
                            for group in sense.get(key, [])[:3]:
                                for obj in group[:6]:
                                    wd = (
                                        obj.get("wd") if isinstance(obj, dict) else None
                                    )
                                    if wd:
                                        target.append(wd)
                    except Exception:
                        continue
        if not synonyms and not antonyms:
            return None

        result = {}
        if synonyms:
            # Remove duplicates while preserving order
            result["synonyms"] = list(dict.fromkeys(synonyms))
        if antonyms:
            # Remove duplicates while preserving order
            result["antonyms"] = list(dict.fromkeys(antonyms))

        return result

    def _extract_mw_fields(self, mw_data: dict[str, Any]) -> dict[str, str]:
        """Extract MW data into individual Anki fields"""
        fields: dict[str, str] = {}

        collegiate_data = mw_data.get("collegiate")
        if collegiate_data and "entries" in collegiate_data:
            entries = collegiate_data["entries"]
            if entries:
                # Use first entry for primary fields
                entry = entries[0]

                # Basic info fields
                if "headword" in entry:
                    fields["MW_Headword"] = entry["headword"]
                if "part_of_speech" in entry:
                    fields["MW_PartOfSpeech"] = entry["part_of_speech"]

                # Stems (word forms)
                if "stems" in entry:
                    fields["MW_Stems"] = ", ".join(entry["stems"])

                # Definitions
                if "definitions" in entry:
                    fields["MW_Definitions"] = " | ".join(entry["definitions"])

                # Inflections
                if "inflections" in entry:
                    inflection_texts = []
                    for inf in entry["inflections"]:
                        text = inf.get("form", "")
                        if inf.get("type"):
                            text += f" ({inf['type']})"
                        if text:
                            inflection_texts.append(text)
                    if inflection_texts:
                        fields["MW_Inflections"] = ", ".join(inflection_texts)

                # Etymology
                if "etymology" in entry:
                    fields["MW_Etymology"] = " ".join(entry["etymology"])

                # First known use
                if "first_known_use" in entry:
                    fields["MW_FirstKnownUse"] = entry["first_known_use"]

                # Examples
                if "examples" in entry:
                    fields["MW_Examples"] = " | ".join(entry["examples"])

                # Learner definitions
                if "learner_definitions" in entry:
                    fields["MW_LearnerDefinitions"] = " | ".join(entry["learner_definitions"])

        # Thesaurus data
        thesaurus_data = mw_data.get("thesaurus")
        if thesaurus_data:
            if "synonyms" in thesaurus_data:
                fields["MW_Synonyms"] = ", ".join(thesaurus_data["synonyms"][:20])  # Limit for field size
            if "antonyms" in thesaurus_data:
                fields["MW_Antonyms"] = ", ".join(thesaurus_data["antonyms"][:20])  # Limit for field size

        return fields

    def _render_mw_html(self, mw_data: dict[str, Any]) -> str:
        """Render MW data to HTML using Jinja2 template."""
        try:
            from jinja2 import Environment, PackageLoader

            # Create Jinja2 environment to load our template
            env = Environment(
                loader=PackageLoader("anki_connector", "templates/base/partials"),
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Load the MW content template
            template = env.get_template("mw_content_standalone.html.j2")

            # Render with MW data
            return template.render(mw_data=mw_data)

        except Exception as e:
            logger.warning(f"Failed to render MW template: {e}")
            return ""

    @staticmethod
    def _mw_markup_to_text(text: str) -> str:
        """Convert common MW inline markup to plain text.

        Examples:
        - {bc} -> space (remove leading colon)
        - {it}italic{/it} -> italic
        - {wi}word{/wi} -> word
        - {a_link|volume} -> volume
        - {sx|large||} -> large
        Unrecognized tags are stripped.
        """
        import re

        s = text
        # Basic containers
        s = s.replace("{bc}", " ")
        s = s.replace("{/it}", "").replace("{it}", "")
        s = s.replace("{/wi}", "").replace("{wi}", "")

        # {a_link|X}
        s = re.sub(r"\{a_link\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)
        # {sx|X|...}
        s = re.sub(r"\{sx\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)

        # Remove any remaining {...}
        s = re.sub(r"\{[^}]+\}", "", s)
        return s.strip()
