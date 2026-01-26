"""
Unit tests for the Transaction dataclass.

Run with: pytest tests/test_transaction.py -v

These tests demonstrate the benefits of using a dataclass:
1. Type validation catches errors early
2. Computed properties simplify code
3. Conversion methods enable gradual migration
"""

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.transaction import Transaction, TransactionType


class TestTransactionCreation:
    """Tests for creating Transaction instances."""

    def test_valid_card_transaction(self):
        """Test creating a valid card transaction."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.00",
            concepto_source="LA CALI SAN JOSE CR",
            detalle="LA CALI SAN JOSE CR",
            referencia="11721252",
            moneda="COLON COSTA RICA",
            tarjeta="9282"
        )

        assert tx.type == "card"
        assert tx.dia == "16/01/2026 22:31:15"
        assert tx.valor == "-4,000.00"
        assert tx.concepto_source == "LA CALI SAN JOSE CR"
        assert tx.detalle == "LA CALI SAN JOSE CR"
        assert tx.referencia == "11721252"
        assert tx.moneda == "COLON COSTA RICA"
        assert tx.tarjeta == "9282"

    def test_valid_sinpe_debit_transaction(self):
        """Test creating a valid SINPE debit transaction."""
        tx = Transaction(
            type="sinpe_debit",
            dia="16/01/2026 14:30:00",
            valor="-50,000.00",
            concepto_source="Pago alquiler",
            detalle="Juan Perez / Pago alquiler",
            referencia="789456123",
            moneda="COLON COSTA RICA",
            tarjeta="3822"
        )

        assert tx.type == "sinpe_debit"
        assert tx.is_expense is True

    def test_valid_sinpe_credit_transaction(self):
        """Test creating a valid SINPE credit transaction."""
        tx = Transaction(
            type="sinpe_credit",
            dia="16/01/2026 10:00:00",
            valor="100,000.00",
            concepto_source="Transferencia",
            detalle="Maria Lopez / Transferencia",
            referencia="456789123",
            moneda="COLON COSTA RICA",
            tarjeta="3822"
        )

        assert tx.type == "sinpe_credit"
        assert tx.is_income is True


class TestTransactionValidation:
    """Tests for Transaction validation (runs in __post_init__)."""

    def test_invalid_type_raises_error(self):
        """Test that invalid transaction type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid transaction type"):
            Transaction(
                type="invalid_type",
                dia="16/01/2026 22:31:15",
                valor="-100.00",
                concepto_source="Store",
                detalle="Store",
                referencia="123456",
                moneda="CRC",
                tarjeta="1234"
            )

    def test_empty_date_raises_error(self):
        """Test that empty date raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Transaction(
                type="card",
                dia="",
                valor="-100.00",
                concepto_source="Store",
                detalle="Store",
                referencia="123456",
                moneda="CRC",
                tarjeta="1234"
            )

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            Transaction(
                type="card",
                dia="2026-01-16",  # Wrong format (should be DD/MM/YYYY)
                valor="-100.00",
                concepto_source="Store",
                detalle="Store",
                referencia="123456",
                moneda="CRC",
                tarjeta="1234"
            )

    def test_empty_valor_raises_error(self):
        """Test that empty valor raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Transaction(
                type="card",
                dia="16/01/2026 22:31:15",
                valor="",
                concepto_source="Store",
                detalle="Store",
                referencia="123456",
                moneda="CRC",
                tarjeta="1234"
            )

    def test_invalid_valor_format_raises_error(self):
        """Test that non-numeric valor raises ValueError."""
        with pytest.raises(ValueError, match="Invalid amount format"):
            Transaction(
                type="card",
                dia="16/01/2026 22:31:15",
                valor="not-a-number",
                concepto_source="Store",
                detalle="Store",
                referencia="123456",
                moneda="CRC",
                tarjeta="1234"
            )

    def test_date_without_time_is_valid(self):
        """Test that date without time component is valid."""
        tx = Transaction(
            type="card",
            dia="16/01/2026",
            valor="-100.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        assert tx.dia == "16/01/2026"


class TestTransactionComputedProperties:
    """Tests for Transaction computed properties."""

    def test_is_expense_for_negative_valor(self):
        """Test is_expense returns True for negative valor."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        assert tx.is_expense is True
        assert tx.is_income is False

    def test_is_income_for_positive_valor(self):
        """Test is_income returns True for positive valor."""
        tx = Transaction(
            type="sinpe_credit",
            dia="16/01/2026 22:31:15",
            valor="50,000.00",
            concepto_source="Transfer",
            detalle="Transfer",
            referencia="123456",
            moneda="CRC",
            tarjeta="3822"
        )
        assert tx.is_income is True
        assert tx.is_expense is False

    def test_amount_numeric_returns_decimal(self):
        """Test amount_numeric returns correct Decimal value."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.50",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        assert tx.amount_numeric == Decimal("-4000.50")

    def test_datetime_parsed_with_time(self):
        """Test datetime_parsed returns correct datetime with time."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-100.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        expected = datetime(2026, 1, 16, 22, 31, 15)
        assert tx.datetime_parsed == expected

    def test_datetime_parsed_without_time(self):
        """Test datetime_parsed works with date only."""
        tx = Transaction(
            type="card",
            dia="16/01/2026",
            valor="-100.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        expected = datetime(2026, 1, 16)
        assert tx.datetime_parsed == expected

    def test_sheet_name_extracts_month_year(self):
        """Test sheet_name extracts MM/YYYY from date."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-100.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        assert tx.sheet_name == "01/2026"

    def test_sheet_name_december(self):
        """Test sheet_name for December."""
        tx = Transaction(
            type="card",
            dia="25/12/2025 10:00:00",
            valor="-100.00",
            concepto_source="Store",
            detalle="Store",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )
        assert tx.sheet_name == "12/2025"


class TestTransactionConversion:
    """Tests for Transaction conversion methods."""

    def test_to_sheet_row(self):
        """Test to_sheet_row returns correct column order."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.00",
            concepto_source="LA CALI",
            detalle="LA CALI SAN JOSE CR",
            referencia="11721252",
            moneda="COLON COSTA RICA",
            tarjeta="9282"
        )

        row = tx.to_sheet_row(category="Domicilios/restaurantes")

        # Column order: Dia | Valor | Concepto | Detalle | Referencia | Moneda | Tarjeta
        assert row == [
            "16/01/2026 22:31:15",
            "-4,000.00",
            "Domicilios/restaurantes",
            "LA CALI SAN JOSE CR",
            "11721252",
            "COLON COSTA RICA",
            "9282"
        ]

    def test_to_dict_roundtrip(self):
        """Test to_dict creates correct dictionary."""
        tx = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.00",
            concepto_source="LA CALI",
            detalle="LA CALI SAN JOSE CR",
            referencia="11721252",
            moneda="COLON COSTA RICA",
            tarjeta="9282"
        )

        d = tx.to_dict()

        assert d == {
            "type": "card",
            "dia": "16/01/2026 22:31:15",
            "valor": "-4,000.00",
            "concepto_source": "LA CALI",
            "detalle": "LA CALI SAN JOSE CR",
            "referencia": "11721252",
            "moneda": "COLON COSTA RICA",
            "tarjeta": "9282"
        }

    def test_from_dict_creates_transaction(self):
        """Test from_dict creates Transaction from dictionary."""
        data = {
            "type": "sinpe_debit",
            "dia": "16/01/2026 14:30:00",
            "valor": "-50,000.00",
            "concepto_source": "Pago alquiler",
            "detalle": "Juan Perez / Pago alquiler",
            "referencia": "789456123",
            "moneda": "COLON COSTA RICA",
            "tarjeta": "3822"
        }

        tx = Transaction.from_dict(data)

        assert tx.type == "sinpe_debit"
        assert tx.dia == "16/01/2026 14:30:00"
        assert tx.valor == "-50,000.00"
        assert tx.referencia == "789456123"

    def test_from_dict_with_missing_optional_fields(self):
        """Test from_dict handles missing optional fields."""
        data = {
            "type": "card",
            "dia": "16/01/2026 22:31:15",
            "valor": "-100.00",
            "referencia": "123456"
            # Missing: concepto_source, detalle, moneda, tarjeta
        }

        tx = Transaction.from_dict(data)

        assert tx.type == "card"
        assert tx.concepto_source == ""
        assert tx.detalle == ""
        assert tx.moneda == ""
        assert tx.tarjeta == ""

    def test_from_dict_with_missing_required_field_raises(self):
        """Test from_dict raises ValueError for missing required fields."""
        data = {
            "type": "card",
            # Missing: dia, valor, referencia
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            Transaction.from_dict(data)

    def test_roundtrip_dict_conversion(self):
        """Test that to_dict -> from_dict produces equivalent Transaction."""
        original = Transaction(
            type="card",
            dia="16/01/2026 22:31:15",
            valor="-4,000.00",
            concepto_source="Store",
            detalle="Store Name",
            referencia="123456",
            moneda="CRC",
            tarjeta="1234"
        )

        restored = Transaction.from_dict(original.to_dict())

        assert original == restored
