"""
Unit tests for the email parser module.

Run with: pytest tests/test_email_parser.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.email_parser import (
    parse_bcr_email,
    EmailParseError,
    validate_transaction_data,
    _clean_text
)


class TestCleanText:
    """Tests for the _clean_text helper function."""

    def test_removes_nbsp(self):
        """Test that &nbsp; is replaced with space."""
        text = "Hello&nbsp;World"
        result = _clean_text(text)
        assert result == "Hello World"

    def test_normalizes_whitespace(self):
        """Test that multiple spaces are normalized."""
        text = "Hello    World"
        result = _clean_text(text)
        assert result == "Hello World"

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "   Hello World   "
        result = _clean_text(text)
        assert result == "Hello World"

    def test_empty_string(self):
        """Test that empty string returns empty."""
        assert _clean_text("") == ""

    def test_none_returns_empty(self):
        """Test that None returns empty string."""
        assert _clean_text(None) == ""


class TestParseBcrEmail:
    """Tests for the parse_bcr_email function."""

    def test_parse_valid_email(self):
        """Test parsing a real BCR email HTML structure."""
        html = """
        <table style="width:100%">
            <thead>
                <tr>
                    <th class="azul">Fecha</th>
                    <th class="azul">Autorización</th>
                    <th class="azul">No.Referencia</th>
                    <th class="azul">Monto</th>
                    <th class="azul">Moneda</th>
                    <th class="azul">Comercio</th>
                    <th class="azul">Estado</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="datos">16/01/2026 22:31:15</td>
                    <td class="datos-num">00918804</td>
                    <td class="datos-num">11721252</td>
                    <td class="datos-num">4,000.00</td>
                    <td class="datos">COLON COSTA RICA</td>
                    <td class="datos">LA CALI SAN JOSE CR</td>
                    <td class="datos">Aprobada</td>
                </tr>
            </tbody>
        </table>
        """
        result = parse_bcr_email(html)

        assert result['date'] == '16/01/2026 22:31:15'
        assert result['authorization'] == '00918804'
        assert result['reference'] == '11721252'
        assert result['amount'] == '4,000.00'
        assert result['currency'] == 'COLON COSTA RICA'
        assert result['merchant'] == 'LA CALI SAN JOSE CR'
        assert result['status'] == 'Aprobada'

    def test_parse_email_with_whitespace(self):
        """Test parsing email with extra whitespace in cells."""
        html = """
        <table>
            <tbody>
                <tr>
                    <td>  16/01/2026 22:31:15  </td>
                    <td>  00918804  </td>
                    <td>  11721252  </td>
                    <td>  4,000.00  </td>
                    <td>  COLON COSTA RICA  </td>
                    <td>  LA CALI SAN JOSE CR  </td>
                    <td>  Aprobada  </td>
                </tr>
            </tbody>
        </table>
        """
        result = parse_bcr_email(html)

        assert result['date'] == '16/01/2026 22:31:15'
        assert result['merchant'] == 'LA CALI SAN JOSE CR'

    def test_parse_empty_html_raises_error(self):
        """Test that empty HTML raises EmailParseError."""
        with pytest.raises(EmailParseError):
            parse_bcr_email("")

    def test_parse_invalid_html_raises_error(self):
        """Test that HTML without transaction data raises error."""
        html = "<html><body><p>No transaction data here</p></body></html>"
        with pytest.raises(EmailParseError):
            parse_bcr_email(html)

    def test_parse_from_fixture_file(self):
        """Test parsing the real BCR email fixture."""
        fixture_path = Path(__file__).parent / 'fixtures' / 'sample_email.html'

        if not fixture_path.exists():
            pytest.skip("Fixture file not found")

        with open(fixture_path) as f:
            html = f.read()

        result = parse_bcr_email(html)

        assert result['date'] == '16/01/2026 22:31:15'
        assert result['merchant'] == 'LA CALI SAN JOSE CR'
        assert result['amount'] == '4,000.00'


class TestValidateTransactionData:
    """Tests for the validate_transaction_data function."""

    def test_valid_transaction(self):
        """Test that valid transaction data passes validation."""
        data = {
            'date': '22/01/2024 14:30:45',
            'authorization': '123456',
            'reference': '789012',
            'amount': '15000.00',
            'currency': 'CRC',
            'merchant': 'MAS X MENOS',
            'status': 'Approved'
        }
        assert validate_transaction_data(data) is True

    def test_missing_required_field(self):
        """Test that missing required field fails validation."""
        data = {
            'date': '22/01/2024 14:30:45',
            'authorization': '123456',
            # missing amount
            'merchant': 'MAS X MENOS',
            'status': 'Approved'
        }
        assert validate_transaction_data(data) is False

    def test_empty_required_field(self):
        """Test that empty required field fails validation."""
        data = {
            'date': '22/01/2024 14:30:45',
            'authorization': '123456',
            'amount': '',  # empty
            'merchant': 'MAS X MENOS',
            'status': 'Approved'
        }
        assert validate_transaction_data(data) is False

    def test_invalid_date_format(self):
        """Test that invalid date format fails validation."""
        data = {
            'date': '2024-01-22',  # wrong format
            'authorization': '123456',
            'amount': '15000.00',
            'merchant': 'MAS X MENOS',
            'status': 'Approved'
        }
        assert validate_transaction_data(data) is False

    def test_invalid_amount_format(self):
        """Test that non-numeric amount fails validation."""
        data = {
            'date': '22/01/2024 14:30:45',
            'authorization': '123456',
            'amount': 'abc',
            'merchant': 'MAS X MENOS',
            'status': 'Approved'
        }
        assert validate_transaction_data(data) is False
