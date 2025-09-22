"""
Tests for Merriam-Webster enricher functionality.
REQUEST URL

https://www.dictionaryapi.com/api/v3/references/collegiate/json/voluminous?key=your-api-key
https://www.dictionaryapi.com/api/v3/references/collegiate/json/buffer?key=a329c0ac-e334-48db-8b4a-05856f385c50
https://www.dictionaryapi.com/api/v3/references/thesaurus/json/umpire?key=your-api-key
https://www.dictionaryapi.com/api/v3/references/thesaurus/json/buffer?key=
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from anki_connector.enrichment.mw_enricher import MerriamWebsterEnricher


class TestMerriamWebsterEnricher:
    """Test class for MerriamWebsterEnricher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.enricher = MerriamWebsterEnricher()

        # Load project test data (main test data)
        test_data_path = (
            Path(__file__).parent
            / "source"
            / "mw_word_project_collegiate_response.json"
        )
        with open(test_data_path) as f:
            self.test_data = json.load(f)

        # Load additional test data files
        self.test_data_files = {}
        for data_file in ["buffer", "design"]:
            file_path = (
                Path(__file__).parent
                / "source"
                / f"mw_word_{data_file}_collegiate_response.json"
            )
            if file_path.exists():
                with open(file_path) as f:
                    self.test_data_files[data_file] = json.load(f)

    def test_markup_to_text_basic(self):
        """Test basic MW markup conversion."""
        # Test basic containers - first {bc} becomes space, rest become colon
        assert self.enricher._mw_markup_to_text("{bc}text") == "text"
        assert self.enricher._mw_markup_to_text("{it}italic{/it}") == "italic"
        assert self.enricher._mw_markup_to_text("{wi}word{/wi}") == "word"

        # Test multiple {bc} - first is space, second is colon
        text = "{bc}a specific plan or design {bc}{sx|scheme||}"
        expected = "a specific plan or design : scheme"
        assert self.enricher._mw_markup_to_text(text) == expected

    def test_markup_bold_colon_handling(self):
        """Test {bc} (bold colon) handling in different contexts."""
        # First {bc} at start -> space (definition marker)
        assert self.enricher._mw_markup_to_text("{bc}to jut out") == "to jut out"

        # Second {bc} in text -> colon (introduces synonym/explanation)
        text = "{bc}to jut out {bc}{sx|protrude||}"
        expected = "to jut out : protrude"
        assert self.enricher._mw_markup_to_text(text) == expected

        # Multiple middle {bc} -> all become colons
        text = "{bc}to come across vividly {bc}give an impression"
        expected = "to come across vividly : give an impression"
        assert self.enricher._mw_markup_to_text(text) == expected

    def test_markup_to_text_links(self):
        """Test MW markup link conversion."""
        # Test a_link markup
        assert self.enricher._mw_markup_to_text("{a_link|volume|1}") == "volume"
        assert self.enricher._mw_markup_to_text("{a_link|test}") == "test"

        # Test sx markup - synonym cross-references show the word
        assert self.enricher._mw_markup_to_text("{sx|large||}") == "large"
        assert self.enricher._mw_markup_to_text("{sx|example||more}") == "example"

    def test_markup_to_text_removes_unknown_tags(self):
        """Test removal of unknown markup tags."""
        assert self.enricher._mw_markup_to_text("{unknown}text{/unknown}") == "text"
        assert self.enricher._mw_markup_to_text("{complex|param1|param2}") == ""
        assert self.enricher._mw_markup_to_text("normal text") == "normal text"

    def test_extract_definition_text(self):
        """Test definition text extraction from dt list."""
        # Valid dt with text - markup gets processed and normalized
        dt_list = [["text", "{bc}a specific plan"]]
        assert self.enricher._extract_definition_text(dt_list) == "a specific plan"

        # Empty dt list
        assert self.enricher._extract_definition_text([]) == ""

        # Non-text dt item
        dt_list = [["vis", "some visual content"]]
        assert self.enricher._extract_definition_text(dt_list) == ""

        # Multiple dt items, first is text
        dt_list = [["text", "definition"], ["vis", "visual"]]
        assert self.enricher._extract_definition_text(dt_list) == "definition"

    def test_parse_full_definitions_basic(self):
        """Test parsing of full definition structure."""
        # Test with empty def list
        assert self.enricher._parse_full_definitions([]) == []

        # Test with malformed def structure
        malformed_def = [{"invalid": "structure"}]
        assert self.enricher._parse_full_definitions(malformed_def) == []

    def test_parse_full_definitions_with_project_data(self):
        """Test parsing using actual project data."""
        # Test noun entry (first entry)
        noun_entry = self.test_data[0]
        definitions = self.enricher._parse_full_definitions(noun_entry.get("def", []))

        assert len(definitions) >= 4  # Should have at least 4 definitions
        assert "1. a specific plan or design" in definitions[0]
        assert "2. idea" in definitions[1]
        assert "3. a planned undertaking: such as" in definitions[2]

        # Test verb entry (second entry) - should have more definitions
        verb_entry = self.test_data[1]
        verb_definitions = self.enricher._parse_full_definitions(
            verb_entry.get("def", [])
        )

        assert (
            len(verb_definitions) >= 11
        )  # Verb should have many definitions (including verb dividers)

        # Filter out verb divider tags
        real_verb_defs = [
            d
            for d in verb_definitions
            if not d.startswith('<span class="mw-verb-divider">')
        ]

        assert len(real_verb_defs) >= 10  # Should have at least 10 real definitions
        assert "1. a. to devise in the mind" in real_verb_defs[0]
        assert "to plan, figure, or estimate for the future" in real_verb_defs[0]

    def test_parse_binding_substitute_structure(self):
        """Test parsing of BS (binding substitute) structure like 'such as'."""
        # Test the third definition which has BS structure
        noun_entry = self.test_data[0]
        definitions = self.enricher._parse_full_definitions(noun_entry.get("def", []))

        # Third definition should be "3. a planned undertaking: such as"
        third_def = definitions[2]
        assert "3. a planned undertaking: such as" in third_def

        # Should have sub-definitions a, b, c
        assert "a definitely formulated piece of research" in third_def
        assert "a large usually government-supported undertaking" in third_def
        assert (
            "a task or problem engaged in usually by a group of students" in third_def
        )

        # Check that sub-definitions are properly formatted with HTML
        assert '<span class="mw-sub-definition">' in third_def
        assert '<span class="mw-sub-marker">a.</span>' in third_def

    def test_parse_full_definitions_respects_limit(self):
        """Test that definition parsing respects the 25-definition limit."""
        # Create a mock entry with many definitions
        mock_def = {
            "sseq": [
                [["sense", {"sn": str(i), "dt": [["text", f"definition {i}"]]}]]
                for i in range(1, 30)  # 29 definitions
            ]
        }

        definitions = self.enricher._parse_full_definitions([mock_def])
        assert len(definitions) == 25  # Should be limited to 25

    def test_parse_empty_structures(self):
        """Test parsing with empty or missing structures."""
        # Empty sseq
        empty_def = {"sseq": []}
        definitions = self.enricher._parse_full_definitions([empty_def])
        assert definitions == []

        # None values
        none_def = {"sseq": None}
        definitions = self.enricher._parse_full_definitions([none_def])
        assert definitions == []

        # Malformed sense items
        malformed_def = {
            "sseq": [
                [["sense", None]],  # None sense_data
                [["sense", {}]],  # Empty sense_data
                [[None, {}]],  # None sense_type
            ]
        }
        definitions = self.enricher._parse_full_definitions([malformed_def])
        assert definitions == []

    def test_thesaurus_empty_structures(self):
        """Test thesaurus parsing with empty or malformed syn_list/ant_list."""
        # Test that empty lists are handled safely
        # This is indirectly tested by checking array bounds in the code
        # The code now checks: if syn_lists and len(syn_lists) > 0 and isinstance(syn_lists[0], list)

        # Create a mock def structure with empty syn/ant lists
        mock_def = [
            {
                "sseq": [
                    [
                        [
                            "sense",
                            {
                                "syn_list": [],  # Empty list
                                "ant_list": [[]],  # List with empty sublist
                            },
                        ]
                    ]
                ]
            }
        ]

        # This should not crash
        result = self.enricher._parse_full_definitions(mock_def)
        # Should return empty since there's no text content
        assert result == []

    def test_extract_mw_fields_basic_info(self):
        """Test extraction of basic MW fields."""
        entry = self.test_data[0]  # noun entry
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Test basic fields
        # MWHeadword removed - assert "MWHeadword" in fields
        # assert "project" in fields["MWHeadword"]  # removed
        # MWPartOfSpeech removed - assert "MWPartOfSpeech" in fields
        # assert fields["MWPartOfSpeech"] == "noun"  # removed
        assert "MWStems" in fields
        assert "project" in fields["MWStems"]

    def test_extract_mw_fields_individual_structured_entries(self):
        """Test extraction of individual structured entry fields."""
        entry = self.test_data[1]  # verb entry with many definitions
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Test individual structured entry fields
        assert "MWStructuredEntry1" in fields

        # Should have structured entry content
        entry_content = fields["MWStructuredEntry1"]
        assert len(entry_content) > 0
        assert "verb" in entry_content.lower()

        # Should have structured entry fields
        structured_entry_fields = [
            k for k in fields.keys() if k.startswith("MWStructuredEntry")
        ]
        assert len(structured_entry_fields) >= 1

        # Test field numbering
        assert "MWStructuredEntry1" in structured_entry_fields

    def test_extract_mw_fields_combined_definitions(self):
        """Test that combined definitions field is still created."""
        entry = self.test_data[0]
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Should have structured entry fields
        structured_entries = [
            k
            for k in fields.keys()
            if k.startswith("MWStructuredEntry") and len(k) > 17 and k[17:].isdigit()
        ]
        assert len(structured_entries) > 0

    def test_extract_mw_fields_definition_limit(self):
        """Test that individual structured entry fields respect the 25 limit."""
        # Use verb entry which has many definitions
        entry = self.test_data[1]
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Count individual structured entry fields
        structured_fields = [
            k
            for k in fields.keys()
            if k.startswith("MWStructuredEntry") and len(k) > 17 and k[17:].isdigit()
        ]

        # Should not exceed 25
        assert len(structured_fields) <= 25

        # Should not have MWStructuredEntry26 or higher
        for i in range(26, 30):
            assert f"MWStructuredEntry{i}" not in fields

    def test_extract_mw_fields_thesaurus_data(self):
        """Test extraction of thesaurus data fields."""
        # Mock thesaurus data
        thesaurus_data = {
            "synonyms": ["plan", "design", "scheme"],
            "antonyms": ["chaos", "disorder"],
        }

        mw_data = {"thesaurus": thesaurus_data}
        fields = self.enricher._extract_mw_fields(mw_data)

        assert "MWSynonyms" in fields
        assert "plan" in fields["MWSynonyms"]
        assert "MWAntonyms" in fields
        assert "chaos" in fields["MWAntonyms"]

    def test_extract_mw_fields_empty_data(self):
        """Test extraction with empty or missing data."""
        # Empty collegiate data
        assert self.enricher._extract_mw_fields({}) == {}
        assert self.enricher._extract_mw_fields({"collegiate": {}}) == {}
        assert self.enricher._extract_mw_fields({"collegiate": {"entries": []}}) == {}

    def test_extract_mw_fields_no_definitions(self):
        """Test extraction with entry that has no definitions."""
        entry_no_defs = {
            "hwi": {"hw": "test"},
            "fl": "noun",
            "meta": {"stems": ["test"]},
            # No "def" field
        }

        fields = self.enricher._extract_mw_fields(
            {"collegiate": {"entries": [entry_no_defs]}}
        )

        # Should have basic fields but no definition fields
        # MWHeadword removed - assert "MWHeadword" in fields
        # MWPartOfSpeech removed - assert "MWPartOfSpeech" in fields
        assert "MWStems" in fields

        def_fields = [k for k in fields.keys() if k.startswith("MWDefinition")]
        assert len(def_fields) == 0

    @patch("anki_connector.enrichment.mw_enricher.settings")
    def test_enrich_disabled(self, mock_settings):
        """Test that enrichment returns empty when disabled."""
        mock_settings.mw.enable = False

        result = self.enricher.enrich("test", None)
        assert result == {}

    @patch("anki_connector.enrichment.mw_enricher.settings")
    def test_enrich_no_keys(self, mock_settings):
        """Test that enrichment returns empty when no API keys configured."""
        mock_settings.mw.enable = True
        mock_settings.mw.collegiate_key = None
        mock_settings.mw.thesaurus_key = None

        result = self.enricher.enrich("test", None)
        assert result == {}

    @patch("anki_connector.enrichment.mw_enricher.requests.get")
    @patch("anki_connector.enrichment.mw_enricher.settings")
    def test_enrich_with_mock_response(self, mock_settings, mock_get):
        """Test enrichment with mocked API response."""
        # Setup mock settings
        mock_settings.mw.enable = True
        mock_settings.mw.collegiate_key = "test_key"
        mock_settings.mw.thesaurus_key = None
        mock_settings.mw.base_url = "https://api.merriam-webster.com/api/references"
        mock_settings.mw.timeout = 10

        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = [self.test_data[0]]  # noun entry
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.enricher.enrich("project", None)

        # Should have extracted fields
        # MWHeadword removed - assert "MWHeadword" in result
        assert "MWStructuredEntry1" in result
        # Verify structured entries exist
        structured_entries = [
            k
            for k in result.keys()
            if k.startswith("MWStructuredEntry") and len(k) > 17 and k[17:].isdigit()
        ]
        assert len(structured_entries) > 0

    def test_field_naming_consistency(self):
        """Test that field naming follows consistent pattern."""
        entry = self.test_data[1]  # verb entry
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Get all definition fields
        def_fields = [
            k
            for k in fields.keys()
            if k.startswith("MWDefinition") and k != "MWDefinitions"
        ]

        # Check naming pattern
        import re

        pattern = re.compile(r"^MWDefinition\d+$")
        for field_name in def_fields:
            assert pattern.match(
                field_name
            ), f"Field {field_name} doesn't match naming pattern"

    def test_definition_content_quality(self):
        """Test that definition content is properly processed."""
        entry = self.test_data[0]
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Check that definitions are non-empty and properly formatted
        def_fields = [
            k
            for k in fields.keys()
            if k.startswith("MWDefinition") and k != "MWDefinitions"
        ]

        for field_name in def_fields:
            definition = fields[field_name]
            assert len(definition.strip()) > 0, f"Definition {field_name} is empty"
            assert not definition.startswith(
                "{"
            ), f"Definition {field_name} contains unprocessed markup"

    def test_shortdef_comparison(self):
        """Test that new approach provides more definitions than shortdef."""
        entry = self.test_data[1]  # verb entry

        # Get shortdef count
        shortdef_count = len(entry.get("shortdef", []))

        # Get new definition count
        definitions = self.enricher._parse_full_definitions(entry.get("def", []))
        new_def_count = len(definitions)

        # New approach should provide more definitions
        assert new_def_count >= shortdef_count
        assert new_def_count > 3  # Should be significantly more for verb entry

    def test_structured_entry_compatibility(self):
        """Test that structured entry fields work correctly."""
        entry = self.test_data[0]
        fields = self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        # Should have structured entry fields
        structured_entries = [
            k
            for k in fields.keys()
            if k.startswith("MWStructuredEntry") and len(k) > 17 and k[17:].isdigit()
        ]
        assert len(structured_entries) > 0

        # Check that structured entries contain content
        has_content = False
        for field_name in structured_entries:
            if fields[field_name].strip():
                has_content = True
                break
        assert has_content


class TestMerriamWebsterEnricherIntegration:
    """Integration tests for MW enricher."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.enricher = MerriamWebsterEnricher()

    def test_full_processing_pipeline(self):
        """Test the complete processing pipeline with real data."""
        test_data_path = (
            Path(__file__).parent
            / "source"
            / "mw_word_project_collegiate_response.json"
        )
        with open(test_data_path) as f:
            data = json.load(f)

        # Test processing all entries
        all_fields = []
        for entry in data[:3]:  # Test first 3 entries
            collegiate_data = {"entries": [entry]}
            fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})
            all_fields.append(fields)

        # Verify each entry produces valid fields
        assert len(all_fields) == 3
        for fields in all_fields:
            assert len(fields) > 0
            # MWHeadword removed - assert "MWHeadword" in fields

    def test_performance_with_multiple_entries(self):
        """Test performance with multiple entries."""
        test_data_path = (
            Path(__file__).parent
            / "source"
            / "mw_word_project_collegiate_response.json"
        )
        with open(test_data_path) as f:
            data = json.load(f)

        import time

        start_time = time.time()

        # Process all entries
        for entry in data:
            self.enricher._extract_mw_fields({"collegiate": {"entries": [entry]}})

        end_time = time.time()
        processing_time = end_time - start_time

        # Should process quickly (less than 1 second for all entries)
        assert processing_time < 1.0

        # Should process at reasonable rate
        entries_per_second = len(data) / processing_time
        assert (
            entries_per_second > 100
        )  # Should process at least 100 entries per second


class TestMerriamWebsterEnricherDataFiles:
    """Test MW enricher with different data files."""

    def setup_method(self):
        """Set up test fixtures."""
        self.enricher = MerriamWebsterEnricher()

    def test_design_data_processing(self):
        """Test processing of design word data."""
        design_file = (
            Path(__file__).parent / "source" / "mw_word_design_collegiate_response.json"
        )

        if not design_file.exists():
            return  # Skip if file doesn't exist

        with open(design_file) as f:
            design_data = json.load(f)

        # Test field extraction
        fields = self.enricher._extract_mw_fields(
            {"collegiate": {"entries": design_data}}
        )

        # Should extract meaningful fields (fewer than before due to new structure)
        assert len(fields) > 10
        # MWHeadword removed - assert "MWHeadword" in fields
        # MWPartOfSpeech removed - assert "MWPartOfSpeech" in fields
        # Should have structured entry fields
        structured_entries = [
            k
            for k in fields.keys()
            if k.startswith("MWStructuredEntry") and len(k) > 17 and k[17:].isdigit()
        ]
        assert len(structured_entries) > 0

        # Should have multiple individual structured entries
        structured_entry_fields = [
            k for k in fields.keys() if k.startswith("MWStructuredEntry")
        ]
        assert len(structured_entry_fields) >= 2  # Should have at least 2 entries

        # Test structured entry quality (should not have unprocessed markup)
        for field_name in structured_entry_fields[:3]:  # Check first 3 entries
            entry_content = fields[field_name]
            assert len(entry_content.strip()) > 0
            assert not entry_content.startswith("{")
            # Should contain HTML structure
            assert "<strong>" in entry_content or "<em>" in entry_content
            assert "}}" not in entry_content  # No stray closing braces

    def test_buffer_data_processing(self):
        """Test processing of buffer word data for specific issues."""
        buffer_file = (
            Path(__file__).parent / "source" / "mw_word_buffer_collegiate_response.json"
        )

        if not buffer_file.exists():
            return  # Skip if file doesn't exist

        with open(buffer_file) as f:
            buffer_data = json.load(f)

        # Test field extraction
        fields = self.enricher._extract_mw_fields(
            {"collegiate": {"entries": buffer_data}}
        )

        # Check for specific buffer issues that were fixed
        # 1. No stray closing braces from {d_link|buffs|buff:3}
        all_defs = " ".join(
            [v for k, v in fields.items() if k.startswith("MWDefinition")]
        )
        assert "}}" not in all_defs, "Should not have stray closing braces"

        # 2. Should have "also" content in some definitions
        has_also_content = any("also:" in v for v in fields.values())
        assert has_also_content, "Should include sdsense 'also' content"

        # 3. Should extract examples (test across all entries)
        all_examples = []
        for entry in buffer_data:
            entry_examples = self.enricher._extract_definition_examples(
                entry.get("def", [])
            )
            all_examples.extend(entry_examples)

        assert len(all_examples) > 0, "Should extract examples from buffer data"

        # Check for long examples (the missing long sentence issue)
        long_examples = [ex for ex in all_examples if len(ex) > 50]
        assert len(long_examples) > 0, "Should have some long examples"

    def test_comprehensive_markup_processing(self):
        """Test comprehensive markup processing across all data files."""
        test_files = [
            "mw_word_project_collegiate_response.json",
            "mw_word_buffer_collegiate_response.json",
            "mw_word_design_collegiate_response.json",
        ]

        for filename in test_files:
            file_path = Path(__file__).parent / "source" / filename
            if not file_path.exists():
                continue

            with open(file_path) as f:
                data = json.load(f)

            # Test that all entries can be processed without errors
            fields = self.enricher._extract_mw_fields({"collegiate": {"entries": data}})

            # Basic sanity checks
            assert len(fields) > 0, f"Should extract fields from {filename}"

            # Check markup processing quality
            for field_name, field_value in fields.items():
                if field_name.startswith("MWDefinition"):
                    # Should not contain unprocessed markup
                    assert (
                        "{d_link" not in field_value
                    ), f"Unprocessed d_link in {filename}"
                    assert (
                        "{sx|" not in field_value
                    ), f"Unprocessed sx markup in {filename}"
                    assert (
                        "{bc}" not in field_value
                    ), f"Unprocessed bc markup in {filename}"

    def test_all_data_files_basic_processing(self):
        """Ensure all MW data files can be processed successfully."""
        test_files = [
            "mw_word_project_collegiate_response.json",
            "mw_word_buffer_collegiate_response.json",
            "mw_word_design_collegiate_response.json",
        ]

        results = {}

        for filename in test_files:
            file_path = Path(__file__).parent / "source" / filename
            if not file_path.exists():
                continue

            try:
                with open(file_path) as f:
                    data = json.load(f)

                # Test processing
                fields = self.enricher._extract_mw_fields(
                    {"collegiate": {"entries": data}}
                )

                # Extract examples from all entries
                all_examples = []
                for entry in data:
                    entry_examples = self.enricher._extract_definition_examples(
                        entry.get("def", [])
                    )
                    all_examples.extend(entry_examples)

                results[filename] = {
                    "fields_count": len(fields),
                    "examples_count": len(all_examples),
                    "has_headword": True,  # MWHeadword removed
                    "has_definitions": any(
                        k.startswith("MWStructuredEntry")
                        and len(k) > 17
                        and k[17:].isdigit()
                        for k in fields.keys()
                    ),
                }

            except Exception as e:
                results[filename] = {"error": str(e)}

        # Verify all files processed successfully
        for filename, result in results.items():
            assert (
                "error" not in result
            ), f"Error processing {filename}: {result.get('error')}"
            assert result["fields_count"] > 0, f"No fields extracted from {filename}"
            assert result["has_headword"], f"Missing headword in {filename}"
            assert result["has_definitions"], f"Missing definitions in {filename}"


class TestMerriamWebsterEnricherVerifyWord:
    """Test MW enricher specifically with the verify word data."""

    def setup_method(self):
        """Set up test fixtures."""
        self.enricher = MerriamWebsterEnricher()

        # Load verify test data
        verify_file = (
            Path(__file__).parent / "source" / "mw_word_verify_collegiate_response.json"
        )
        if verify_file.exists():
            with open(verify_file) as f:
                self.verify_data = json.load(f)
        else:
            self.verify_data = None

    def test_verify_data_exists(self):
        """Test that verify word data file exists and is valid."""
        assert self.verify_data is not None, "Verify word data file should exist"
        assert len(self.verify_data) > 0, "Verify data should have at least one entry"
        assert isinstance(
            self.verify_data[0], dict
        ), "First entry should be a dictionary"

    def test_verify_data_structure(self):
        """Test that verify word data has correct structure."""
        entry = self.verify_data[0]

        # Test required fields
        required_fields = ["meta", "hwi", "fl", "def", "shortdef"]
        for field in required_fields:
            assert field in entry, f"Entry should have {field} field"

        # Test meta structure
        meta = entry["meta"]
        assert "id" in meta, "Meta should have id"
        assert meta["id"] == "verify", "Meta id should be 'verify'"
        assert "stems" in meta, "Meta should have stems"
        assert "verify" in meta["stems"], "Stems should include 'verify'"

        # Test headword structure
        hwi = entry["hwi"]
        assert "hw" in hwi, "Headword info should have hw field"
        assert "ver*i*fy" in hwi["hw"], "Headword should contain 'ver*i*fy'"

        # Test part of speech
        assert entry["fl"] == "verb", "Part of speech should be verb"

    def test_verify_pronunciation_extraction(self):
        """Test pronunciation extraction from verify data."""
        entry = self.verify_data[0]
        hwi = entry.get("hwi", {})
        prs = hwi.get("prs", [])

        assert len(prs) > 0, "Should have pronunciation data"
        first_pr = prs[0]
        assert "mw" in first_pr, "Should have MW pronunciation"
        assert "ˈver-ə-ˌfī" in first_pr["mw"], "Should have correct pronunciation"

        # Test audio file reference
        sound = first_pr.get("sound", {})
        assert "audio" in sound, "Should have audio reference"
        assert sound["audio"] == "verify01", "Should have correct audio filename"

    def test_verify_definition_parsing(self):
        """Test definition parsing from verify data."""
        entry = self.verify_data[0]
        definitions = self.enricher._parse_full_definitions(entry.get("def", []))

        assert (
            len(definitions) >= 3
        ), "Should have at least 3 items (verb divider + 2 definitions)"

        # Filter out verb divider tags
        real_definitions = [
            d for d in definitions if not d.startswith('<span class="mw-verb-divider">')
        ]

        assert len(real_definitions) >= 2, "Should have at least 2 real definitions"

        # Test first definition
        first_def = real_definitions[0]
        assert "1. to establish the truth, accuracy, or reality of" in first_def

        # Test second definition
        second_def = real_definitions[1]
        assert "2. to confirm or substantiate in law by oath" in second_def

    def test_verify_field_extraction(self):
        """Test field extraction for verify word."""
        collegiate_data = {"entries": self.verify_data}
        fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})

        # Test basic fields
        assert "MWStems" in fields, "Should extract stems"
        assert "verify" in fields["MWStems"], "Stems should include 'verify'"

        assert "MWPronunciation" in fields, "Should extract pronunciation"
        assert (
            "ˈver-ə-ˌfī" in fields["MWPronunciation"]
        ), "Should have correct pronunciation"

        assert "MWStructuredEntry1" in fields, "Should have structured entry"

    def test_verify_structured_entry_content(self):
        """Test structured entry content for verify word."""
        collegiate_data = {"entries": self.verify_data}
        fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})

        structured_entry = fields["MWStructuredEntry1"]

        # Test HTML structure
        assert (
            "<strong>ver*i*fy</strong>" in structured_entry
        ), "Should have formatted headword"
        assert "<em>(verb)</em>" in structured_entry, "Should have part of speech"

        # Test definition content
        assert "to establish the truth, accuracy, or reality of" in structured_entry
        assert "to confirm or substantiate in law by oath" in structured_entry

        # Test no unprocessed markup
        markup_issues = ["{bc}", "{wi}", "{/wi}", "{{", "}}"]
        for issue in markup_issues:
            assert (
                issue not in structured_entry
            ), f"Should not contain unprocessed markup: {issue}"

    def test_verify_etymology_extraction(self):
        """Test etymology extraction for verify word."""
        collegiate_data = {"entries": self.verify_data}
        fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})

        assert "MWEtymology" in fields, "Should extract etymology"
        etymology = fields["MWEtymology"]

        # Test expected etymology content
        assert "Middle English" in etymology, "Should mention Middle English"
        assert "verifien" in etymology, "Should mention Old English form"
        assert "Medieval Latin" in etymology, "Should mention Medieval Latin"
        assert "vērificāre" in etymology, "Should mention Latin root"

    def test_verify_synonyms_extraction(self):
        """Test synonyms extraction for verify word."""
        collegiate_data = {"entries": self.verify_data}
        fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})

        assert "MWCollegiateSynonyms" in fields, "Should extract synonyms"
        synonyms = fields["MWCollegiateSynonyms"]

        # Test expected synonyms content
        expected_words = [
            "confirm",
            "corroborate",
            "substantiate",
            "authenticate",
            "validate",
        ]
        for word in expected_words:
            assert word in synonyms, f"Should mention synonym: {word}"

    def test_verify_shortdef_comparison(self):
        """Test that parsed definitions match shortdef for verify word."""
        entry = self.verify_data[0]

        # Get shortdef
        shortdef = entry.get("shortdef", [])

        # Get parsed definitions
        parsed_defs = self.enricher._parse_full_definitions(entry.get("def", []))

        assert len(parsed_defs) >= len(
            shortdef
        ), "Should have at least as many parsed definitions as shortdef"

        # Test that key content from shortdef appears in parsed definitions
        for short_def in shortdef:
            found_in_parsed = any(short_def in parsed_def for parsed_def in parsed_defs)
            assert (
                found_in_parsed
            ), f"Shortdef '{short_def}' should appear in parsed definitions"

    def test_verify_processing_performance(self):
        """Test performance of processing verify data."""
        import time

        start_time = time.time()

        # Process the data multiple times
        for _ in range(10):
            collegiate_data = {"entries": self.verify_data}
            self.enricher._extract_mw_fields({"collegiate": collegiate_data})

        end_time = time.time()
        processing_time = end_time - start_time

        # Should process quickly (less than 0.1 seconds for 10 iterations)
        assert (
            processing_time < 0.1
        ), f"Processing should be fast, took {processing_time:.3f}s"

    def test_verify_markup_processing(self):
        """Test specific markup processing for verify word data."""
        entry = self.verify_data[0]

        # Test markup conversion on actual verify data content
        test_markups = [
            ("{bc}to establish the truth", "to establish the truth"),
            ("{wi}verify{/wi} the claim", "verify the claim"),
            ("{it}verify{/it}", "verify"),
        ]

        for markup, expected in test_markups:
            result = self.enricher._mw_markup_to_text(markup)
            assert (
                result == expected
            ), f"Markup '{markup}' should convert to '{expected}', got '{result}'"

    def test_verify_integration_with_existing_tests(self):
        """Test that verify data integrates well with existing test patterns."""
        # Test that verify data can be processed alongside other test data
        verify_file = (
            Path(__file__).parent / "source" / "mw_word_verify_collegiate_response.json"
        )
        project_file = (
            Path(__file__).parent
            / "source"
            / "mw_word_project_collegiate_response.json"
        )

        if project_file.exists():
            with open(project_file) as f:
                project_data = json.load(f)

            # Combine datasets
            combined_data = (
                self.verify_data + project_data[:2]
            )  # Just first 2 project entries

            # Test processing
            collegiate_data = {"entries": combined_data}
            fields = self.enricher._extract_mw_fields({"collegiate": collegiate_data})

            # Should have fields from all entries
            assert len(fields) > 0, "Should extract fields from combined data"

            # Should have multiple structured entries
            structured_entries = [
                k for k in fields.keys() if k.startswith("MWStructuredEntry")
            ]
            assert (
                len(structured_entries) >= 3
            ), "Should have multiple structured entries"
