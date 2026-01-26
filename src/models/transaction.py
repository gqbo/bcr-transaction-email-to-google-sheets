"""
Transaction dataclass for BCR bank transaction data.

This module provides a typed, validated data structure for transactions,
replacing the previous Dict[str, str] approach.

Benefits over dictionaries:
- Type safety: IDE catches typos and type errors
- Validation: Invalid data is caught at creation time
- Documentation: Fields are self-documenting
- Methods: Can add computed properties and helper methods
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
import re
import logging

logger = logging.getLogger(__name__)

# Type alias for transaction types
TransactionType = Literal["card", "sinpe_debit", "sinpe_credit"]


@dataclass
class Transaction:
    """
    Represents a parsed bank transaction.

    This dataclass replaces the Dict[str, str] pattern used throughout
    the codebase, providing type safety and validation.

    Attributes:
        type: The kind of transaction ("card", "sinpe_debit", "sinpe_credit")
        dia: Date and time in format "DD/MM/YYYY HH:MM:SS"
        valor: Amount as string with sign ("-15,000.00" for expenses)
        concepto_source: Text used for AI categorization (merchant or motivo)
        detalle: Human-readable description for display
        referencia: Bank reference number
        moneda: Currency ("COLON COSTA RICA", "US DOLLAR")
        tarjeta: Last 4 digits of card or account identifier ("SINPEMOVIL" for SINPE)

    Example:
        >>> tx = Transaction(
        ...     type="card",
        ...     dia="16/01/2026 22:31:15",
        ...     valor="-4,000.00",
        ...     concepto_source="LA CALI SAN JOSE CR",
        ...     detalle="LA CALI SAN JOSE CR",
        ...     referencia="11721252",
        ...     moneda="COLON COSTA RICA",
        ...     tarjeta="9282"
        ... )
        >>> tx.is_expense
        True
        >>> tx.sheet_name
        '01/2026'
    """

    type: TransactionType
    dia: str
    valor: str
    concepto_source: str
    detalle: str
    referencia: str
    moneda: str
    tarjeta: str

    def __post_init__(self):
        """
        Validation that runs after __init__.

        Ensures data is valid before the transaction is used anywhere.
        This follows the "fail fast" principle - catch problems early.
        """
        self._validate_type()
        self._validate_date()
        self._validate_valor()

    def _validate_type(self) -> None:
        """Ensure type is one of the allowed values."""
        valid_types = ("card", "sinpe_debit", "sinpe_credit")
        if self.type not in valid_types:
            raise ValueError(
                f"Invalid transaction type: '{self.type}'. "
                f"Must be one of: {valid_types}"
            )

    def _validate_date(self) -> None:
        """Ensure dia is in the expected format."""
        if not self.dia:
            raise ValueError("Transaction date (dia) cannot be empty")

        # Pattern: DD/MM/YYYY or DD/MM/YYYY HH:MM:SS
        pattern = r'^\d{1,2}/\d{2}/\d{4}(\s+\d{1,2}:\d{2}:\d{2})?$'
        if not re.match(pattern, self.dia):
            raise ValueError(
                f"Invalid date format: '{self.dia}'. "
                f"Expected: DD/MM/YYYY HH:MM:SS"
            )

    def _validate_valor(self) -> None:
        """Ensure valor is a valid numeric format."""
        if not self.valor:
            raise ValueError("Transaction amount (valor) cannot be empty")

        # Remove formatting to check if it's numeric
        cleaned = self.valor.replace(',', '').replace(' ', '').replace('-', '')
        try:
            float(cleaned)
        except ValueError:
            raise ValueError(
                f"Invalid amount format: '{self.valor}'. "
                f"Expected numeric value like '-15,000.00'"
            )

    # ============================================================
    # Computed Properties
    # ============================================================

    @property
    def is_expense(self) -> bool:
        """
        Return True if this is a money-out transaction.

        Card transactions and SINPE debits are expenses (negative valor).
        """
        return self.valor.startswith('-')

    @property
    def is_income(self) -> bool:
        """
        Return True if this is a money-in transaction.

        SINPE credits are income (positive valor).
        """
        return not self.is_expense

    @property
    def amount_numeric(self) -> Decimal:
        """
        Return the amount as a Decimal for calculations.

        Why Decimal instead of float?
        - Float has precision issues: 0.1 + 0.2 = 0.30000000000000004
        - Decimal is exact: Decimal('0.1') + Decimal('0.2') = Decimal('0.3')
        - Critical for financial calculations!
        """
        cleaned = self.valor.replace(',', '').replace(' ', '')
        return Decimal(cleaned)

    @property
    def datetime_parsed(self) -> datetime:
        """
        Parse the date string into a datetime object.

        Useful for sorting transactions chronologically.
        """
        # Handle both "DD/MM/YYYY" and "DD/MM/YYYY HH:MM:SS"
        if ' ' in self.dia:
            return datetime.strptime(self.dia, "%d/%m/%Y %H:%M:%S")
        return datetime.strptime(self.dia, "%d/%m/%Y")

    @property
    def sheet_name(self) -> str:
        """
        Get the sheet name (MM/YYYY) for this transaction.

        Used to determine which Google Sheet tab to write to.
        """
        parts = self.dia.split('/')
        if len(parts) >= 3:
            month = parts[1]
            year = parts[2].split()[0]  # Remove time part if present
            return f"{month}/{year}"
        return "Unknown"

    # ============================================================
    # Conversion Methods
    # ============================================================

    def to_sheet_row(self, category: str) -> list[str]:
        """
        Convert to a row for Google Sheets.

        Column order: Dia | Valor | Concepto | Detalle | Referencia | Moneda | Tarjeta

        Args:
            category: The AI-determined category for "Concepto" column

        Returns:
            List of strings in the correct column order
        """
        return [
            self.dia,
            self.valor,
            category,
            self.detalle,
            self.referencia,
            self.moneda,
            self.tarjeta,
        ]

    def to_dict(self) -> dict[str, str]:
        """
        Convert to a dictionary for backward compatibility.

        This allows gradual migration - new code uses the dataclass,
        old code can still receive dictionaries.
        """
        return {
            "type": self.type,
            "dia": self.dia,
            "valor": self.valor,
            "concepto_source": self.concepto_source,
            "detalle": self.detalle,
            "referencia": self.referencia,
            "moneda": self.moneda,
            "tarjeta": self.tarjeta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Transaction":
        """
        Create a Transaction from a dictionary.

        This is the bridge for migration - parse functions can keep
        returning dicts, and we convert them to Transaction objects.

        Args:
            data: Dictionary with transaction fields

        Returns:
            Transaction instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = ['type', 'dia', 'valor', 'referencia']
        missing = [f for f in required_fields if f not in data or not data[f]]

        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        return cls(
            type=data['type'],
            dia=data['dia'],
            valor=data['valor'],
            concepto_source=data.get('concepto_source', ''),
            detalle=data.get('detalle', ''),
            referencia=data['referencia'],
            moneda=data.get('moneda', ''),
            tarjeta=data.get('tarjeta', ''),
        )
