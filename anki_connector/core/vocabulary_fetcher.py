"""Fetch vocabulary data from vocabulary.com"""

import os
import re
import time
from typing import Any

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util import Retry

from ..config.settings import settings
from ..core.text_processor import TextProcessor
from ..models.word_info import Phonetics, WordDefinition, WordForms, WordInfo
from .constants import VocabularyConstants
from .interfaces import VocabularyFetcherInterface


class VocabularyFetcher(VocabularyFetcherInterface):
    """Fetches comprehensive word information from vocabulary.com"""

    def __init__(
        self,
        timeout: int | None = None,
    ):
        self.timeout = int(
            timeout if timeout is not None else settings.vocabulary.request_timeout
        )
        self.session = requests.Session()
        self.text_processor = TextProcessor()
        # Configure headers to appear as a regular browser
        headers = VocabularyConstants.DEFAULT_HEADERS.copy()
        headers["User-Agent"] = VocabularyConstants.DEFAULT_USER_AGENT
        headers["Referer"] = "https://www.vocabulary.com/"
        self.session.headers.update(headers)
        # Optional authentication cookie if needed (set `VOCAB_COOKIE` env var)
        cookie = os.environ.get("VOCAB_COOKIE")
        if cookie:
            self.session.headers.update({"Cookie": cookie})
        self._configure_retries()

    def fetch_word_info(self, word: str) -> WordInfo | None:
        """Fetch word information from vocabulary.com AJAX endpoint"""
        try:
            return self._fetch_from_ajax_endpoint(word)

        except (requests.RequestException, requests.Timeout) as e:
            from ..logging_config import get_logger

            get_logger(__name__).warning(f"Network error fetching {word}: {e}")
            return None
        except (ValueError, KeyError) as e:
            from ..logging_config import get_logger

            get_logger(__name__).warning(f"Data parsing error for {word}: {e}")
            return None
        except Exception as e:
            from ..logging_config import get_logger

            get_logger(__name__).error(f"Unexpected error fetching {word}: {e}")
            return None

    def _fetch_from_ajax_endpoint(self, word: str) -> WordInfo | None:
        """Fetch and parse word data from vocabulary.com AJAX endpoint"""
        word_data = self._get_ajax_response(word)
        if word_data and (word_data.get("parts") or word_data.get("additions")):
            return self._dict_to_word_info(word_data)
        return None

    def _extract_phonetics(self, soup: BeautifulSoup) -> list[str]:
        """Extract phonetics from vocabulary.com's IPA section (US/UK)."""
        results: list[str] = []
        # Try both .ipa-section and .ipa-section-with-def containers
        sections = soup.select(".ipa-section, .ipa-section-with-def")
        if not sections:
            return results

        for section in sections:
            for block in section.select(".ipa-with-audio"):
                # Find the span that contains the actual phonetic transcription (starts with /)
                ipa_spans = block.select(".span-replace-h3")
                ipa = None
                for span in ipa_spans:
                    text = span.get_text(strip=True)
                    if text.startswith("/") and text.endswith("/"):
                        ipa = text
                        break

                if not ipa:
                    continue
                label = (
                    "US"
                    if block.select_one(".us-flag-icon")
                    else ("UK" if block.select_one(".uk-flag-icon") else None)
                )
                if label:
                    results.append(f"{label}: {ipa}")
                else:
                    # If no flag icon, just add the phonetic without label
                    results.append(ipa)
        # Deduplicate by full string (label + phonetic), preserving different labels
        seen_full_entries = set()
        out: list[str] = []
        for r in results:
            if r not in seen_full_entries:
                out.append(r)
                seen_full_entries.add(r)
        return out

    def _extract_definitions(
        self, soup: BeautifulSoup, target_word: str
    ) -> list[WordDefinition]:
        """Extract definitions from all .word-definitions containers, including examples and synonyms/antonyms."""
        out: list[WordDefinition] = []
        # Handle multiple .word-definitions containers (e.g., different pronunciations/parts of speech)
        for wrap in soup.select(".word-definitions"):
            for li in wrap.select("ol > li"):
                pos_el = li.select_one(".pos-icon")
                pos = (
                    self._clean_part_of_speech(pos_el.get_text(strip=True))
                    if pos_el
                    else ""
                )
                def_el = li.select_one(".definition")
                if not def_el:
                    continue
                # Exclude pos-icon text from the definition text
                parts: list[str] = []
                for child in def_el.children:
                    # Skip <span class="pos-icon"> inside definition block
                    if isinstance(child, Tag):
                        raw_classes = child.get("class")
                        classes: list[str]
                        if isinstance(raw_classes, str):
                            classes = [raw_classes]
                        elif isinstance(raw_classes, list):
                            classes = raw_classes
                        else:
                            classes = []
                        if "pos-icon" in classes:
                            continue
                    get_text = getattr(child, "get_text", None)
                    parts.append(
                        get_text(strip=True) if callable(get_text) else str(child)
                    )
                definition = self.text_processor.clean_text(
                    " ".join([p for p in parts if p])
                )
                if not definition:
                    continue

                # Examples within this sense
                examples: list[str] = []
                for ex in li.select(".defContent .example"):
                    t = ex.get_text(" ", strip=True)
                    t = self.text_processor.clean_text(t)
                    if t and t not in examples:
                        examples.append(t)

                # Synonyms/antonyms within this sense (handle continuation groups).
                # Ignore 'types'/'type of'.
                synonyms: list[str] = []
                antonyms: list[str] = []
                last_section: str | None = None  # 'synonyms' | 'antonyms' | None
                for inst in li.select(".div-replace-dl.instances"):
                    label_el = inst.select_one(".detail")
                    label_txt = (
                        label_el.get_text(strip=True).lower() if label_el else ""
                    )
                    section: str | None = None
                    if "synonym" in label_txt:
                        section = "synonyms"
                        last_section = section
                    elif "antonym" in label_txt:
                        section = "antonyms"
                        last_section = section
                    elif label_txt == "":
                        # Continuation block without label: inherit previous section
                        section = last_section
                    else:
                        # Other labeled sections (e.g., 'types', 'type of') are ignored
                        section = None

                    if not section:
                        continue

                    words = [a.get_text(strip=True) for a in inst.select("a.word")]
                    if not words:
                        continue

                    if section == "synonyms":
                        for w in words:
                            if w and w not in synonyms:
                                synonyms.append(w)
                    elif section == "antonyms":
                        for w in words:
                            if w and w not in antonyms:
                                antonyms.append(w)

                out.append(
                    WordDefinition(
                        part_of_speech=pos,
                        definition=definition,
                        examples=examples[: VocabularyConstants.MAX_EXAMPLES],
                        synonyms=synonyms[: VocabularyConstants.MAX_SYNONYMS],
                        antonyms=antonyms[: VocabularyConstants.MAX_ANTONYMS],
                    )
                )
                if len(out) >= VocabularyConstants.MAX_DEFINITIONS:
                    break
        return out

    def _extract_word_forms(self, soup: BeautifulSoup) -> list[str]:
        """Extract word forms from <p class="word-forms">Other forms: ...</p>.

        Prefer bolded items; fall back to parsing trailing text.
        """
        forms: list[str] = []
        for pf in soup.select("p.word-forms"):
            vals = []
            # Extract text from bold tags and split semicolon-separated forms
            for b in pf.select("b"):
                bold_text = b.get_text(strip=True)
                # Split semicolon or comma separated forms within bold tags
                split_forms = [
                    v.strip() for v in re.split(r"[;,]\s*", bold_text) if v.strip()
                ]
                vals.extend(split_forms)

            if not vals:
                txt = pf.get_text(" ", strip=True)
                m = re.search(r"Other\s+forms:\s*(.+)$", txt, re.I)
                if m:
                    payload = m.group(1)
                    vals = [
                        v.strip() for v in re.split(r"[;,]\s*", payload) if v.strip()
                    ]
            for v in vals or []:
                if v and v not in forms:
                    forms.append(v)
        # Filter out the headword and dedupe
        head = soup.select_one("#hdr-word-area")
        head_text = head.get_text(strip=True).lower() if head else ""
        clean: list[str] = []
        for f in forms:
            fv = f.strip()
            if fv and fv.lower() != head_text and fv not in clean:
                clean.append(fv)
        return clean[: VocabularyConstants.MAX_WORD_FORMS]

    def _extract_additional_info(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract short and long blurbs from page paragraphs .short and .long."""
        out: dict[str, str] = {}
        se = soup.select_one(".short")
        if se:
            out["short_explanation"] = self.text_processor.clean_text(
                se.get_text(" ", strip=True)
            )
        le = soup.select_one(".long")
        if le:
            out["long_explanation"] = self.text_processor.clean_text(
                le.get_text(" ", strip=True)
            )
        return out

    def _parse_vocab_soup(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Parse vocabulary.com HTML content and extract word information"""
        head = soup.select_one("#hdr-word-area")
        head_text = head.get_text(strip=True) if head else ""

        # Extract all available data from the parsed HTML
        definitions = self._extract_definitions(soup, "")
        parts_dict = [
            {
                "part": d.part_of_speech,
                "definition": d.definition,
                "examples": d.examples,
                "synonyms": d.synonyms,
                "antonyms": d.antonyms,
            }
            for d in definitions
        ]

        return {
            "word": head_text,
            "phonetics": self._extract_phonetics(soup),
            "parts": parts_dict,
            "exchanges": self._extract_word_forms(soup),
            "additions": self._extract_additional_info(soup),
        }

    def _dict_to_word_info(self, data: dict[str, Any]) -> WordInfo:
        """Convert parsed word data to WordInfo object"""
        definitions = []
        for part_data in data.get("parts", []):
            definition = WordDefinition(
                part_of_speech=part_data.get("part", ""),
                definition=part_data.get("definition", ""),
                examples=part_data.get("examples", []),
                synonyms=part_data.get("synonyms", []),
                antonyms=part_data.get("antonyms", []),
            )
            definitions.append(definition)

        additions = data.get("additions", {})

        # Create proper phonetics object
        phonetics_data = data.get("phonetics", [])
        us_phonetic = next(
            (p.replace("US: ", "") for p in phonetics_data if "US:" in p), None
        )
        uk_phonetic = next(
            (p.replace("UK: ", "") for p in phonetics_data if "UK:" in p), None
        )

        # Handle unlabeled phonetics (assign to available slot)
        unlabeled_phonetics = [p for p in phonetics_data if ":" not in p]
        if unlabeled_phonetics:
            if not us_phonetic:
                us_phonetic = unlabeled_phonetics[0]
            elif not uk_phonetic:
                uk_phonetic = unlabeled_phonetics[0]
            else:
                # If both slots are taken, append to US phonetic
                us_phonetic += f" / {unlabeled_phonetics[0]}"

        phonetics = Phonetics(us=us_phonetic, uk=uk_phonetic)

        # Create proper word forms object
        word_forms = WordForms(forms=data.get("exchanges", []))

        return WordInfo(
            word=data.get("word", ""),
            phonetics=phonetics,
            definitions=definitions,
            word_forms=word_forms,
            short_explanation=additions.get("short_explanation"),
            long_explanation=additions.get("long_explanation"),
            etymology=additions.get("etymology"),
            source=data.get("source") or "vocabulary.com",
        )

    def _clean_part_of_speech(self, part: str) -> str:
        """Clean and standardize part of speech"""
        if not part:
            return ""

        part = part.lower().strip()
        part = re.sub(r"[^\w\s]", "", part)  # Remove punctuation

        # Common abbreviations mapping
        pos_map = {
            "n": "noun",
            "noun": "noun",
            "v": "verb",
            "verb": "verb",
            "adj": "adjective",
            "adjective": "adjective",
            "adv": "adverb",
            "adverb": "adverb",
            "prep": "preposition",
            "preposition": "preposition",
            "conj": "conjunction",
            "conjunction": "conjunction",
            "pron": "pronoun",
            "pronoun": "pronoun",
            "interj": "interjection",
            "interjection": "interjection",
        }

        return pos_map.get(part, part)

    def _get_ajax_response(self, word: str) -> dict[str, Any] | None:
        """Get and parse response from vocabulary.com AJAX endpoint"""
        try:
            url = f"{VocabularyConstants.VOCABULARY_AJAX_URL}?search={word}&lang=en"
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.content, "html.parser")
            data = self._parse_vocab_soup(soup)
            data["word"] = word
            # AJAX response contains the available data for this word
            return data if (data.get("parts") or data.get("additions")) else None
        except Exception:
            return None

    def batch_fetch(
        self, words: list[str], delay: float = 1.0
    ) -> dict[str, WordInfo | None]:
        """Fetch information for multiple words with rate limiting"""
        results: dict[str, WordInfo | None] = {}

        from ..logging_config import get_logger

        logger = get_logger(__name__)
        for i, word in enumerate(words, 1):
            logger.info(f"Fetching ({i}/{len(words)}): {word}")
            results[word] = self.fetch_word_info(word)

            if i < len(words):  # Don't delay after the last word
                time.sleep(delay)

        return results

    def _configure_retries(self) -> None:
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
