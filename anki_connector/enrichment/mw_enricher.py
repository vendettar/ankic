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

# Constants for MW data processing
MAX_SENSES_PER_DEFINITION = 3
MAX_SYNONYMS_PER_SENSE = 12
MAX_ANTONYMS_PER_SENSE = 12
MAX_DEFINITIONS_FOR_ANKI = 25
MAX_SYNONYM_GROUPS = 4
MAX_WORDS_PER_SYNONYM_GROUP = 6


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

    def _is_main_entry(self, entry: dict[str, Any], word: str) -> bool:
        """
        Determine if this entry is a main definition of the searched word.

        Main entries are direct definitions of the word itself, not compound words,
        phrases, or geographic names. Uses structural fields:
        - Exact word match: meta.id == "{word}" (single definition)
        - Homograph: presence of 'hom' field indicates numbered main entry
        """
        meta = entry.get("meta", {})
        entry_id = meta.get("id", "")

        # Single definition case: exact match
        if entry_id == word:
            return True

        # Multiple definitions case: has homograph number
        # The 'hom' field indicates this is a main entry with multiple definitions
        if entry.get("hom") is not None:
            # Verify the id starts with the word (to exclude related entries)
            return bool(entry_id.startswith(word + ":"))

        return False

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
        # Process entries with official website filtering logic
        for entry in data:
            # Skip geographic names
            fl = entry.get("fl", "")
            if fl == "geographical name":
                continue

            # Apply official website filtering if enabled
            if settings.mw.official_website_mode and not self._is_main_entry(
                entry, word
            ):
                continue
            entry_data: dict[str, Any] = {}

            # Cache commonly accessed nested dictionaries
            hwi = entry.get("hwi") or {}
            meta = entry.get("meta") or {}
            fl = entry.get("fl") or ""

            # Extract headword and part of speech
            headword = hwi.get("hw") or ""
            if headword:
                # Clean pronunciation markers from headword
                entry_data["headword"] = headword.replace("*", "")
            if fl:
                entry_data["part_of_speech"] = fl

            # Extract stems
            stems = meta.get("stems") or []
            if stems:
                entry_data["stems"] = stems

            # Extract pronunciation (IPA) - hwi already cached
            prs = hwi.get("prs") or []
            pronunciations = []
            for pr in prs:
                if "mw" in pr:
                    pronunciations.append(pr["mw"])
            if pronunciations:
                entry_data["pronunciations"] = pronunciations

            # Extract inflections (ins) - different from uros
            ins = entry.get("ins") or []
            word_inflections = []
            for inflection in ins:
                if_form = inflection.get("if", "")
                if if_form:
                    word_inflections.append(if_form)
            if word_inflections:
                entry_data["word_inflections"] = word_inflections

            # Extract definitions from full def structure
            definitions = self._parse_full_definitions(entry.get("def", []))
            if definitions:
                entry_data["definitions"] = definitions

            # Extract examples from definitions
            examples = self._extract_definition_examples(entry.get("def", []))
            if examples:
                entry_data["examples"] = examples

            # Extract collegiate synonyms paragraph (different from thesaurus)
            syns = entry.get("syns") or []
            if syns and len(syns) > 0:
                syn_paragraph = self._extract_synonyms_paragraph(syns[0])
                if syn_paragraph:
                    entry_data["collegiate_synonyms"] = syn_paragraph

            # Extract etymology
            et_list = entry.get("et") or []
            et_texts = []
            for et in et_list:
                if isinstance(et, list) and et and et[0] == "text":
                    et_texts.append(self._mw_markup_to_text(et[1]))
                elif isinstance(et, dict) and "text" in et:
                    et_texts.append(self._mw_markup_to_text(et.get("text", "")))
            if et_texts:
                entry_data["etymology"] = et_texts

            # Extract examples
            suppl = entry.get("suppl") or {}
            examples = []
            for ex in (suppl.get("examples") or [])[:MAX_SYNONYM_GROUPS]:
                t = ex.get("t")
                if t:
                    examples.append(self._mw_markup_to_text(t))
            if examples:
                entry_data["examples"] = examples
            ldq = suppl.get("ldq") or {}
            ld_defs: list[str] = []
            for d in (ldq.get("def") or [])[:2]:
                for sseq_item in d.get("sseq", [])[:MAX_SENSES_PER_DEFINITION]:
                    if not isinstance(sseq_item, list):
                        continue

                    # Iterate through sense items structurally
                    for item in sseq_item:
                        if not isinstance(item, list) or len(item) < 2:
                            continue

                        sense_type = item[0]
                        sense_data = item[1]

                        if sense_type == "sense" and isinstance(sense_data, dict):
                            dt = sense_data.get("dt", [])
                            for dt_item in dt:
                                if (
                                    isinstance(dt_item, list)
                                    and len(dt_item) >= 2
                                    and dt_item[0] == "text"
                                ):
                                    ld_defs.append(self._mw_markup_to_text(dt_item[1]))
                                    break
                            break  # Only take first sense per sseq_item
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

        # Process thesaurus data - prefer detailed sense lists over meta shortcuts
        for entry in data:
            # First try detailed sense lists from def structure (more accurate)
            def_processed = False
            for d in entry.get("def", []) or []:
                for sseq_item in d.get("sseq", [])[
                    :MAX_SENSES_PER_DEFINITION
                ]:  # Limit to first 3 senses
                    if not isinstance(sseq_item, list):
                        continue

                    # Iterate through sense items in this sseq_item
                    for item in sseq_item:
                        if not isinstance(item, list) or len(item) < 2:
                            continue

                        sense_type = item[0]
                        sense_data = item[1]

                        if sense_type == "sense" and isinstance(sense_data, dict):
                            # Extract synonyms from syn_list
                            syn_lists = sense_data.get("syn_list", [])
                            if (
                                syn_lists
                                and len(syn_lists) > 0
                                and isinstance(syn_lists[0], list)
                            ):
                                for obj in syn_lists[0][:MAX_SYNONYMS_PER_SENSE]:
                                    if isinstance(obj, dict):
                                        wd = obj.get("wd")
                                        if wd:
                                            synonyms.append(wd)

                            # Extract antonyms from ant_list
                            ant_lists = sense_data.get("ant_list", [])
                            if (
                                ant_lists
                                and len(ant_lists) > 0
                                and isinstance(ant_lists[0], list)
                            ):
                                for obj in ant_lists[0][:MAX_ANTONYMS_PER_SENSE]:
                                    if isinstance(obj, dict):
                                        wd = obj.get("wd")
                                        if wd:
                                            antonyms.append(wd)

                            def_processed = True

            # Fallback to meta shortcuts only if def processing didn't work
            if not def_processed:
                meta = entry.get("meta") or {}
                for group in meta.get("syns", [])[:MAX_SYNONYM_GROUPS]:
                    for s in group[:MAX_WORDS_PER_SYNONYM_GROUP]:
                        synonyms.append(s)
                for group in meta.get("ants", [])[:MAX_SYNONYM_GROUPS]:
                    for a in group[:MAX_WORDS_PER_SYNONYM_GROUP]:
                        antonyms.append(a)

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

    def _parse_full_definitions(self, def_list: list[dict[str, Any]]) -> list[str]:
        """Parse the full def structure to extract all numbered definitions.

        Uses structural approach: sseq index for main numbering, sense items for sub-letters.
        For verbs, handles vd (verb divider) field to distinguish between
        transitive verb, intransitive verb, etc.
        """
        definitions = []

        for def_entry in def_list:
            # Check if this def_entry has a verb divider (vd)
            vd = def_entry.get("vd")
            if vd:
                # Add verb divider as a separator
                definitions.append(f'<span class="mw-verb-divider">{vd}</span>')

            sseq = def_entry.get("sseq", [])

            # Handle None or non-list sseq
            if not sseq or not isinstance(sseq, list):
                continue

            # Use sseq index for main numbering (1, 2, 3, ...)
            for main_idx, seq_item in enumerate(sseq, 1):
                if not seq_item or not isinstance(seq_item, list):
                    continue

                # Check if first item is "bs" (binding substitute) - special case
                has_bs = False
                bs_sense_data = None
                regular_sense_items = []

                for item in seq_item:
                    if not isinstance(item, list) or len(item) < 2:
                        continue

                    sense_type = item[0]
                    sense_data = item[1]

                    if sense_type == "bs" and isinstance(sense_data, dict):
                        # BS is a header definition (like "such as")
                        has_bs = True
                        bs_sense_obj = sense_data.get("sense", {})
                        if isinstance(bs_sense_obj, dict):
                            bs_sense_data = bs_sense_obj
                    elif sense_type == "sense" and isinstance(sense_data, dict):
                        regular_sense_items.append(sense_data)

                # Handle BS + multiple senses case (e.g., "3. a planned undertaking: such as")
                if has_bs and bs_sense_data and regular_sense_items:
                    # BS text is the main definition, regular senses are sub-items
                    dt_list = bs_sense_data.get("dt", [])
                    main_text = self._extract_definition_text(dt_list)

                    if main_text:
                        main_def_parts = [f"{main_idx}. {main_text}"]

                        # Add sub-definitions a, b, c...
                        for sub_idx, sense_data in enumerate(regular_sense_items):
                            dt_list = sense_data.get("dt", [])
                            def_text = self._extract_definition_text(dt_list)
                            if not def_text:
                                continue

                            sub_letter = chr(ord("a") + sub_idx)
                            sub_html = (
                                f'<span class="mw-sub-definition">'
                                f'<span class="mw-sub-marker">{sub_letter}.</span>'
                                f'<span class="mw-sub-text">{def_text}</span>'
                                f"</span>"
                            )
                            main_def_parts.append(sub_html)

                        combined_def = main_def_parts[0]
                        for part in main_def_parts[1:]:
                            combined_def += "<br>" + part
                        definitions.append(combined_def)
                    continue

                # Normal case: collect all senses (no BS, or BS without sub-senses)
                sense_items = []
                if bs_sense_data:
                    sense_items.append(bs_sense_data)
                sense_items.extend(regular_sense_items)

                if not sense_items:
                    continue

                # Build definition: main number + optional sub-letters
                if len(sense_items) == 1:
                    # Single definition: just "1. text"
                    sense_data = sense_items[0]
                    dt_list = sense_data.get("dt", [])
                    def_text = self._extract_definition_text(dt_list)

                    # Check for sdsense (also content)
                    sdsense = sense_data.get("sdsense", {})
                    if sdsense and isinstance(sdsense, dict):
                        sdsense_dt = sdsense.get("dt", [])
                        sdsense_text = self._extract_definition_text(sdsense_dt)
                        if sdsense_text:
                            if def_text:
                                def_text = f"{def_text}; also: {sdsense_text}"
                            else:
                                def_text = f"also: {sdsense_text}"

                    if def_text:
                        definitions.append(f"{main_idx}. {def_text}")
                else:
                    # Multiple sub-definitions: "1. a. text" + sub-items
                    main_def_parts = []

                    for sub_idx, sense_data in enumerate(sense_items):
                        dt_list = sense_data.get("dt", [])
                        def_text = self._extract_definition_text(dt_list)

                        # Check for sdsense
                        sdsense = sense_data.get("sdsense", {})
                        if sdsense and isinstance(sdsense, dict):
                            sdsense_dt = sdsense.get("dt", [])
                            sdsense_text = self._extract_definition_text(sdsense_dt)
                            if sdsense_text:
                                if def_text:
                                    def_text = f"{def_text}; also: {sdsense_text}"
                                else:
                                    def_text = f"also: {sdsense_text}"

                        if not def_text:
                            continue

                        # Use letters a, b, c, ...
                        sub_letter = chr(ord("a") + sub_idx)

                        if sub_idx == 0:
                            # First item: "1. a. text"
                            main_def_parts.append(
                                f"{main_idx}. {sub_letter}. {def_text}"
                            )
                        else:
                            # Subsequent items: formatted as sub-definition
                            sub_html = (
                                f'<span class="mw-sub-definition">'
                                f'<span class="mw-sub-marker">{sub_letter}.</span>'
                                f'<span class="mw-sub-text">{def_text}</span>'
                                f"</span>"
                            )
                            main_def_parts.append(sub_html)

                    if main_def_parts:
                        # Join with <br> between sub-definitions
                        combined_def = main_def_parts[0]
                        for part in main_def_parts[1:]:
                            combined_def += "<br>" + part
                        definitions.append(combined_def)

        return definitions[
            :MAX_DEFINITIONS_FOR_ANKI
        ]  # Limit to 25 for Anki template compatibility

    def _extract_definition_text(self, dt_list: list) -> str:
        """Extract definition text from dt (definition text) list."""
        for dt_item in dt_list:
            if isinstance(dt_item, list) and len(dt_item) >= 2:
                if dt_item[0] == "text":
                    return self._mw_markup_to_text(dt_item[1])
        return ""

    def _extract_definition_examples(self, def_list: list[dict[str, Any]]) -> list[str]:
        """Extract example sentences from definition structure."""
        examples = []

        for def_entry in def_list:
            sseq = def_entry.get("sseq", [])

            for seq_item in sseq:
                if not seq_item or not isinstance(seq_item, list):
                    continue

                for sense_item in seq_item:
                    if not isinstance(sense_item, list) or len(sense_item) < 2:
                        continue

                    sense_type = sense_item[0]
                    sense_data = sense_item[1]

                    if sense_type == "sense" and isinstance(sense_data, dict):
                        # Check main dt list for examples
                        dt_list = sense_data.get("dt", [])
                        for dt_item in dt_list:
                            if isinstance(dt_item, list) and len(dt_item) >= 2:
                                if dt_item[0] == "vis":  # Visual examples
                                    vis_examples = dt_item[1]
                                    for vis in vis_examples:
                                        if isinstance(vis, dict) and "t" in vis:
                                            example_text = self._mw_markup_to_text(
                                                vis["t"]
                                            )
                                            if example_text:
                                                examples.append(example_text)

                        # Also check sdsense (subject/status labeled sense) for examples
                        sdsense = sense_data.get("sdsense", {})
                        if sdsense and isinstance(sdsense, dict):
                            sdsense_dt = sdsense.get("dt", [])
                            for dt_item in sdsense_dt:
                                if isinstance(dt_item, list) and len(dt_item) >= 2:
                                    if (
                                        dt_item[0] == "vis"
                                    ):  # Visual examples in sdsense
                                        vis_examples = dt_item[1]
                                        for vis in vis_examples:
                                            if isinstance(vis, dict) and "t" in vis:
                                                example_text = self._mw_markup_to_text(
                                                    vis["t"]
                                                )
                                                if example_text:
                                                    examples.append(example_text)

        return examples

    def _extract_synonyms_paragraph(self, syns_data: dict[str, Any]) -> str:
        """Extract the detailed synonyms explanation paragraph from collegiate dictionary with proper formatting."""
        pt = syns_data.get("pt", [])
        if not pt:
            return ""

        formatted_parts = []
        current_text = ""

        for item in pt:
            if isinstance(item, list) and len(item) >= 2:
                if item[0] == "text":
                    # Clean text and add to current section
                    text_content = self._mw_markup_to_text(item[1]).strip()
                    if text_content:
                        current_text = text_content

                elif item[0] == "vis":  # Visual examples follow the text
                    vis_items = item[1]
                    examples = []
                    for vis in vis_items:
                        if isinstance(vis, dict) and "t" in vis:
                            example = self._mw_markup_to_text(vis["t"]).strip()
                            if example:
                                examples.append(f'<em>"{example}"</em>')

                    # Combine current text with its examples
                    if current_text:
                        if examples:
                            # Add examples on new line with indentation
                            section = f"{current_text}<br>    {' | '.join(examples)}"
                        else:
                            section = current_text
                        formatted_parts.append(section)
                        current_text = ""

        # Handle any remaining text without examples
        if current_text:
            formatted_parts.append(current_text)

        return "<br><br>".join(formatted_parts)

    def _extract_mw_fields(self, mw_data: dict[str, Any]) -> dict[str, str]:
        """Extract MW data into individual Anki fields"""
        fields: dict[str, str] = {}

        collegiate_data = mw_data.get("collegiate")
        if collegiate_data and "entries" in collegiate_data:
            raw_entries = collegiate_data["entries"]

            # Check if entries are already processed (have 'headword' key) or raw (have 'hwi' key)
            if raw_entries and isinstance(raw_entries[0], dict):
                if "headword" in raw_entries[0]:
                    # Already processed entries
                    entries = raw_entries
                elif "hwi" in raw_entries[0]:
                    # Raw MW API entries - need to process them first
                    entries = []
                    for raw_entry in raw_entries:
                        entry_data = {}

                        # Extract headword and part of speech
                        headword = (raw_entry.get("hwi") or {}).get("hw") or ""
                        fl = raw_entry.get("fl") or ""
                        if headword:
                            entry_data["headword"] = headword
                        if fl:
                            entry_data["part_of_speech"] = fl

                        # Extract stems
                        stems = raw_entry.get("meta", {}).get("stems") or []
                        if stems:
                            entry_data["stems"] = stems

                        # Extract definitions
                        definitions = self._parse_full_definitions(
                            raw_entry.get("def", [])
                        )
                        if definitions:
                            entry_data["definitions"] = definitions

                        # Extract pronunciation (IPA)
                        hwi = raw_entry.get("hwi") or {}
                        prs = hwi.get("prs") or []
                        pronunciations = []
                        for pr in prs:
                            if "mw" in pr:
                                pronunciations.append(pr["mw"])
                        if pronunciations:
                            entry_data["pronunciations"] = pronunciations

                        # Extract collegiate synonyms paragraph
                        syns = raw_entry.get("syns") or []
                        if syns and len(syns) > 0:
                            syn_paragraph = self._extract_synonyms_paragraph(syns[0])
                            if syn_paragraph:
                                entry_data["collegiate_synonyms"] = syn_paragraph

                        # Extract etymology
                        et_list = raw_entry.get("et") or []
                        et_texts = []
                        for et in et_list:
                            if isinstance(et, list) and et and et[0] == "text":
                                et_texts.append(self._mw_markup_to_text(et[1]))
                        if et_texts:
                            entry_data["etymology"] = et_texts

                        if entry_data:
                            entries.append(entry_data)
                else:
                    entries = []
            else:
                entries = []
            if entries:
                # Process each entry separately and assign to individual entry fields
                entry_blocks = []

                # Process each entry individually
                for _entry_idx, entry in enumerate(entries, 1):
                    # Extract headword from entry - already processed in _fetch_collegiate_data
                    headword = entry.get("headword", "")

                    # Extract part of speech - already processed in _fetch_collegiate_data
                    part_of_speech = entry.get("part_of_speech", "")

                    # Extract definitions - already processed in _fetch_collegiate_data
                    entry_definitions = entry.get("definitions", [])

                    # Create entry block with header
                    if headword and part_of_speech and entry_definitions:
                        entry_header = (
                            f"<strong>{headword}</strong> <em>({part_of_speech})</em>"
                        )
                        entry_parts = [entry_header]
                        entry_parts.extend(entry_definitions)
                        entry_blocks.append("<br>".join(entry_parts))

                # 1. Basic MW info fields
                basic_mw_data = {}
                if entries:
                    # All stems combined
                    all_stems = []
                    for entry in entries:
                        stems = entry.get("stems", [])
                        all_stems.extend(stems)
                    if all_stems:
                        unique_stems = list(dict.fromkeys(all_stems))
                        basic_mw_data["MWStems"] = ", ".join(unique_stems)

                fields.update(basic_mw_data)

                # 2. MW structured entry fields (individual entries with their definitions)
                structured_entry_data = {}
                if entry_blocks:
                    # Create individual structured entry fields (MWStructuredEntry1, MWStructuredEntry2, etc.)
                    # Limited to 25 for Anki template compatibility
                    for i, entry_block in enumerate(
                        entry_blocks[:MAX_DEFINITIONS_FOR_ANKI], 1
                    ):
                        structured_entry_data[f"MWStructuredEntry{i}"] = entry_block

                fields.update(structured_entry_data)

                # 4. MW extended info fields (from primary entry)
                extended_mw_data = {}
                if entries:
                    primary_entry = entries[0]

                    # Pronunciation (IPA) from primary entry
                    pronunciations = primary_entry.get("pronunciations", [])
                    if pronunciations:
                        extended_mw_data["MWPronunciation"] = " | ".join(pronunciations)

                    # Word inflections from primary entry (ins field)
                    word_inflections = primary_entry.get("word_inflections", [])
                    if word_inflections:
                        # Clean MW asterisk formatting
                        clean_inflections = [
                            infl.replace("*", "") for infl in word_inflections
                        ]
                        extended_mw_data["MWWordInflections"] = ", ".join(
                            clean_inflections
                        )

                    # Examples from primary entry
                    examples = primary_entry.get("examples", [])
                    if examples:
                        extended_mw_data["MWExamples"] = " | ".join(examples)

                    # Etymology from primary entry
                    etymology = primary_entry.get("etymology", [])
                    if etymology:
                        extended_mw_data["MWEtymology"] = " ".join(etymology)

                    # Collegiate synonyms paragraph (detailed explanation)
                    collegiate_synonyms = primary_entry.get("collegiate_synonyms", "")
                    if collegiate_synonyms:
                        extended_mw_data["MWCollegiateSynonyms"] = collegiate_synonyms

                    # Learner definitions from primary entry
                    learner_defs = primary_entry.get("learner_definitions", [])
                    if learner_defs:
                        extended_mw_data["MWLearnerDefinitions"] = " | ".join(
                            learner_defs
                        )

                fields.update(extended_mw_data)

        # 4. Thesaurus data
        thesaurus_data = mw_data.get("thesaurus")
        if thesaurus_data:
            thesaurus_fields = {}
            if "synonyms" in thesaurus_data:
                thesaurus_fields["MWSynonyms"] = ", ".join(thesaurus_data["synonyms"])
            if "antonyms" in thesaurus_data:
                thesaurus_fields["MWAntonyms"] = ", ".join(thesaurus_data["antonyms"])

            fields.update(thesaurus_fields)

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
        """Convert MW inline markup to plain text.

        Comprehensive handling of Merriam-Webster markup patterns found in API responses.
        Processes both paired tags like {it}text{/it} and parameter tags like {sx|word||}.

        Examples:
        - {bc} -> space (first occurrence) or " : " (subsequent - introduces synonyms/explanations)
        - {it}italic{/it} -> italic
        - {wi}word{/wi} -> word
        - {a_link|volume} -> volume
        - {sx|large||} -> large
        - {d_link|buffs|buff:3} -> buffs
        - {ds||1||} -> (removed - date/section markers)
        - {sc}small caps{/sc} -> small caps
        - {mat|jet|} -> jet

        All unrecognized tags are stripped.
        """
        import re

        if not text or not isinstance(text, str):
            return ""

        s = text

        # Step 1: Handle paired container tags (opening and closing)
        # Basic text styling
        s = re.sub(r"\{it\}(.*?)\{/it\}", r"\1", s)  # Italic text
        s = re.sub(r"\{wi\}(.*?)\{/wi\}", r"\1", s)  # Word info
        s = re.sub(r"\{sc\}(.*?)\{/sc\}", r"\1", s)  # Small caps

        # Step 2: Handle standalone markers
        # {bc} at the start means "definition follows", replace with space
        # {bc} in the middle means colon (introduces synonym or explanation)
        # Replace first {bc} with space, rest with colon
        if "{bc}" in s:
            s = s.replace("{bc}", " ", 1)  # First occurrence -> space
            s = s.replace("{bc}", " : ")  # Rest -> colon with spaces

        # Step 3: Handle parameterized tags (with pipes)
        # Cross-reference links
        s = re.sub(r"\{a_link\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)  # Article links
        s = re.sub(
            r"\{sx\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s
        )  # Synonym cross-references
        s = re.sub(
            r"\{d_link\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s
        )  # Dictionary entry links
        s = re.sub(
            r"\{dx\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s
        )  # Directional cross-references
        s = re.sub(r"\{et_link\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)  # Etymology links
        s = re.sub(r"\{mat\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)  # Related entry links

        # Additional reference types
        s = re.sub(
            r"\{dxt\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s
        )  # Directional cross-references (variant)
        s = re.sub(r"\{inf\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)  # Inflection links
        s = re.sub(r"\{ma\|([^}|]+)(?:\|[^}]*)?\}", r"\1", s)  # Main entry links

        # Step 4: Handle structural markers that should be removed entirely
        s = re.sub(r"\{ds\|[^}]*\}", "", s)  # Date/section markers
        s = re.sub(r"\{ldquo\}", '"', s)  # Left double quote
        s = re.sub(r"\{rdquo\}", '"', s)  # Right double quote
        s = re.sub(r"\{ldq\}", '"', s)  # Left quote (variant)
        s = re.sub(r"\{rdq\}", '"', s)  # Right quote (variant)

        # Step 5: Clean up any orphaned closing tags
        s = re.sub(r"\{/[^}]+\}", "", s)  # Remove orphaned closing tags

        # Step 6: Remove any remaining unrecognized tags
        s = re.sub(r"\{[^}]*\}", "", s)

        # Step 7: Clean up whitespace but preserve meaningful spacing
        s = re.sub(r"\s+", " ", s)  # Normalize multiple spaces
        return s.strip()  # Remove leading/trailing whitespace
