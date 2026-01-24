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


class TestBatchAppendTransactions:
    """Tests for the batch_append_transactions method."""

    @pytest.fixture
    def mock_writer(self, monkeypatch):
        """Create a SheetsWriter with mocked dependencies."""
        monkeypatch.setenv('SPREADSHEET_ID', 'test-id')
        monkeypatch.setenv('GOOGLE_TOKEN', '{"token": "fake"}')

        monkeypatch.setattr(
            SheetsWriter,
            '_build_service',
            lambda self: None
        )
        return SheetsWriter()

    def test_empty_list_returns_empty(self, mock_writer):
        """Test that empty input returns empty succeeded and failed lists."""
        succeeded, failed = mock_writer.batch_append_transactions([])
        assert succeeded == []
        assert failed == []

    def test_groups_transactions_by_sheet(self, mock_writer, monkeypatch):
        """Test that transactions are grouped by their target sheet."""
        sheets_called = []

        def mock_ensure_sheet_exists(sheet_name):
            return True

        def mock_batch_append_rows(rows, sheet_name):
            sheets_called.append((sheet_name, len(rows)))
            return True, 2

        monkeypatch.setattr(mock_writer, '_ensure_sheet_exists', mock_ensure_sheet_exists)
        monkeypatch.setattr(mock_writer, '_batch_append_rows', mock_batch_append_rows)

        transactions = [
            ({'id': '1'}, {'dia': '15/01/2026 10:00:00', 'detalle': 'Store A'}, 'Food'),
            ({'id': '2'}, {'dia': '16/01/2026 11:00:00', 'detalle': 'Store B'}, 'Food'),
            ({'id': '3'}, {'dia': '20/12/2025 12:00:00', 'detalle': 'Store C'}, 'Transport'),
        ]

        succeeded, failed = mock_writer.batch_append_transactions(transactions)

        # Should have called batch append for 2 different sheets
        assert len(sheets_called) == 2
        sheet_names = [s[0] for s in sheets_called]
        assert '01/2026' in sheet_names
        assert '12/2025' in sheet_names

        # Check row counts per sheet
        sheet_dict = {s[0]: s[1] for s in sheets_called}
        assert sheet_dict['01/2026'] == 2  # Two transactions in January
        assert sheet_dict['12/2025'] == 1  # One transaction in December

        assert len(succeeded) == 3
        assert len(failed) == 0

    def test_failed_sheet_creation_adds_to_failed(self, mock_writer, monkeypatch):
        """Test that transactions go to failed list when sheet creation fails."""
        def mock_ensure_sheet_exists(sheet_name):
            return False

        monkeypatch.setattr(mock_writer, '_ensure_sheet_exists', mock_ensure_sheet_exists)

        transactions = [
            ({'id': '1'}, {'dia': '15/01/2026 10:00:00', 'detalle': 'Store A'}, 'Food'),
        ]

        succeeded, failed = mock_writer.batch_append_transactions(transactions)

        assert len(succeeded) == 0
        assert len(failed) == 1

    def test_failed_batch_append_adds_to_failed(self, mock_writer, monkeypatch):
        """Test that transactions go to failed list when batch append fails."""
        def mock_ensure_sheet_exists(sheet_name):
            return True

        def mock_batch_append_rows(rows, sheet_name):
            return False, None

        monkeypatch.setattr(mock_writer, '_ensure_sheet_exists', mock_ensure_sheet_exists)
        monkeypatch.setattr(mock_writer, '_batch_append_rows', mock_batch_append_rows)

        transactions = [
            ({'id': '1'}, {'dia': '15/01/2026 10:00:00', 'detalle': 'Store A'}, 'Food'),
        ]

        succeeded, failed = mock_writer.batch_append_transactions(transactions)

        assert len(succeeded) == 0
        assert len(failed) == 1


class TestBatchAppendRows:
    """Tests for the _batch_append_rows method."""

    @pytest.fixture
    def mock_writer(self, monkeypatch):
        """Create a SheetsWriter with mocked dependencies."""
        monkeypatch.setenv('SPREADSHEET_ID', 'test-id')
        monkeypatch.setenv('GOOGLE_TOKEN', '{"token": "fake"}')

        monkeypatch.setattr(
            SheetsWriter,
            '_build_service',
            lambda self: None
        )
        return SheetsWriter()

    def test_empty_rows_returns_success(self, mock_writer):
        """Test that empty rows list returns success."""
        success, row_num = mock_writer._batch_append_rows([], '01/2026')
        assert success is True
        assert row_num is None
