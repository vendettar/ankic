"""Test MW enricher official website mode filtering"""

import pytest
from anki_connector.enrichment.mw_enricher import MerriamWebsterEnricher
from anki_connector.config.settings import settings


class TestMWOfficialMode:
    """Test MW enricher official website mode functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.enricher = MerriamWebsterEnricher()
        # Store original setting
        self.original_mode = settings.mw.official_website_mode

    def teardown_method(self):
        """Clean up after tests"""
        # Restore original setting
        settings.mw.official_website_mode = self.original_mode

    def test_is_main_entry_logic(self):
        """Test the main entry identification logic"""
        test_cases = [
            # (entry_data, word, expected_result, description)
            (
                {"meta": {"id": "design:1"}, "hom": 1},
                "design",
                True,
                "Main homograph entry with hom field",
            ),
            (
                {"meta": {"id": "design:2"}, "hom": 2},
                "design",
                True,
                "Second homograph entry",
            ),
            (
                {"meta": {"id": "graphic design"}},
                "design",
                False,
                "Compound word without hom field",
            ),
            ({"meta": {"id": "by design"}}, "design", False, "Idiom without hom field"),
            ({"meta": {"id": "codesign"}}, "design", False, "Related word"),
            (
                {"meta": {"id": "design:1"}},  # No hom field
                "design",
                False,
                "Pattern matches but no hom field",
            ),
            ({"meta": {"id": "cat:1"}, "hom": 1}, "design", False, "Wrong word"),
        ]

        for entry_data, word, expected, description in test_cases:
            result = self.enricher._is_main_entry(entry_data, word)
            assert result == expected, f"Failed: {description}"

    def test_filtering_with_mock_data(self):
        """Test filtering behavior with mock data"""
        # Mock data representing typical MW API response
        mock_data = [
            {
                "meta": {"id": "test:1", "stems": ["test"]},
                "hom": 1,
                "fl": "noun",
                "hwi": {"hw": "test"},
            },
            {
                "meta": {"id": "test:2", "stems": ["test"]},
                "hom": 2,
                "fl": "verb",
                "hwi": {"hw": "test"},
            },
            {
                "meta": {"id": "testing", "stems": ["testing"]},
                "fl": "noun",
                "hwi": {"hw": "testing"},
            },
            {
                "meta": {"id": "test case", "stems": ["test case"]},
                "fl": "noun",
                "hwi": {"hw": "test case"},
            },
        ]

        # Mock the _fetch_json method
        original_fetch = self.enricher._fetch_json

        def mock_fetch_json(ref, word, key):
            if ref == "collegiate" and word == "test":
                return mock_data
            return None

        self.enricher._fetch_json = mock_fetch_json

        try:
            # Test official mode
            settings.mw.official_website_mode = True
            collegiate_data_official = self.enricher._fetch_collegiate_data("test")

            assert collegiate_data_official is not None
            entries_official = collegiate_data_official.get("entries", [])
            assert len(entries_official) == 2  # Only main entries

            # Verify only main entries are included
            headwords_official = [
                entry.get("headword", "") for entry in entries_official
            ]
            assert "test" in headwords_official  # Should have main entries
            assert "testing" not in " ".join(
                headwords_official
            )  # Should not have related words

            # Test complete mode
            settings.mw.official_website_mode = False
            collegiate_data_complete = self.enricher._fetch_collegiate_data("test")

            assert collegiate_data_complete is not None
            entries_complete = collegiate_data_complete.get("entries", [])
            assert len(entries_complete) == 4  # All entries except geographic

            # Verify all entries are included
            headwords_complete = [
                entry.get("headword", "") for entry in entries_complete
            ]
            assert len(headwords_complete) == 4

        finally:
            # Restore original method
            self.enricher._fetch_json = original_fetch

    def test_geographic_filtering_still_works(self):
        """Test that geographic names are still filtered out in both modes"""
        mock_data = [
            {
                "meta": {"id": "test:1", "stems": ["test"]},
                "hom": 1,
                "fl": "noun",
                "hwi": {"hw": "test"},
            },
            {
                "meta": {"id": "Test City", "stems": ["Test City"]},
                "fl": "geographical name",
                "hwi": {"hw": "Test City"},
            },
        ]

        original_fetch = self.enricher._fetch_json

        def mock_fetch_json(ref, word, key):
            if ref == "collegiate" and word == "test":
                return mock_data
            return None

        self.enricher._fetch_json = mock_fetch_json

        try:
            # Test both modes exclude geographic names
            for mode in [True, False]:
                settings.mw.official_website_mode = mode
                collegiate_data = self.enricher._fetch_collegiate_data("test")

                assert collegiate_data is not None
                entries = collegiate_data.get("entries", [])

                # Geographic names should be filtered out in both modes
                for entry in entries:
                    assert entry.get("part_of_speech") != "geographical name"

        finally:
            self.enricher._fetch_json = original_fetch
