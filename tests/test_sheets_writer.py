"""
Unit tests for the sheets writer module.

Run with: pytest tests/test_sheets_writer.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sheets_writer import SheetsWriter


class TestGetSheetNameFromDate:
    """Tests for the _get_sheet_name_from_date method."""

    @pytest.fixture
    def mock_writer(self, monkeypatch):
        """Create a SheetsWriter with mocked dependencies."""
        monkeypatch.setenv('SPREADSHEET_ID', 'test-id')
        monkeypatch.setenv('GOOGLE_TOKEN', '{"token": "fake"}')

        # Mock the _build_service method to avoid API calls
        monkeypatch.setattr(
            SheetsWriter,
            '_build_service',
            lambda self: None
        )
        return SheetsWriter()

    def test_standard_date_format(self, mock_writer):
        """Test extracting sheet name from standard BCR date format."""
        result = mock_writer._get_sheet_name_from_date('16/01/2026 22:31:15')
        assert result == '01/2026'

    def test_different_month(self, mock_writer):
        """Test extracting sheet name from a different month."""
        result = mock_writer._get_sheet_name_from_date('25/12/2025 10:00:00')
        assert result == '12/2025'

    def test_february(self, mock_writer):
        """Test February date."""
        result = mock_writer._get_sheet_name_from_date('01/02/2026 08:15:30')
        assert result == '02/2026'

    def test_date_only_no_time(self, mock_writer):
        """Test date without time component."""
        result = mock_writer._get_sheet_name_from_date('16/01/2026')
        assert result == '01/2026'

    def test_empty_string_returns_unknown(self, mock_writer):
        """Test that empty string returns 'Unknown'."""
        result = mock_writer._get_sheet_name_from_date('')
        assert result == 'Unknown'

    def test_invalid_format_returns_unknown(self, mock_writer):
        """Test that invalid format returns 'Unknown'."""
        result = mock_writer._get_sheet_name_from_date('2026-01-16')
        assert result == 'Unknown'
