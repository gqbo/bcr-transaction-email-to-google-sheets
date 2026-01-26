"""
Email parser for BCR bank transaction notifications.

This module extracts structured transaction data from BCR email HTML
for both card transactions and SINPE mobile transactions.
"""

import re
import logging
from typing import Dict, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EmailParseError(Exception):
    """Error raised when email parsing fails."""
    pass


class DeniedTransactionError(Exception):
    """Error raised when a transaction is denied and should be skipped."""
    pass


def detect_email_type(html_content: str, subject: str) -> str:
    """
    Detect the type of BCR email.

    Args:
        html_content: HTML content of the email
        subject: Email subject line

    Returns:
        "card", "sinpe_debit", or "sinpe_credit"
    """
    if "SINPEMOVIL" in subject or "SINPE" in subject.upper():
        # Check if debit or credit based on content
        if "debitado" in html_content.lower():
            return "sinpe_debit"
        elif "acreditado" in html_content.lower():
            return "sinpe_credit"
        # Fallback: check for destination vs origin
        if "Destino" in html_content:
            return "sinpe_debit"
        elif "origen" in html_content.lower():
            return "sinpe_credit"
    return "card"


def parse_bcr_email(html_content: str, subject: str = "") -> Dict[str, str]:
    """
    Extract structured transaction data from BCR email HTML.

    Automatically detects the email type and routes to the appropriate parser.

    Args:
        html_content: Complete HTML string from email
        subject: Email subject line (optional, helps with type detection)

    Returns:
        Dictionary with unified fields:
        {
            "type": "card" | "sinpe_debit" | "sinpe_credit",
            "dia": "DD/MM/YYYY HH:MM:SS",
            "valor": "-15,000.00" | "15,000.00",
            "concepto_source": "merchant or motivo for AI categorization",
            "detalle": "merchant or cliente/motivo",
            "referencia": "reference number"
        }

    Raises:
        EmailParseError: If email cannot be parsed
        DeniedTransactionError: If transaction was denied (should be skipped)
    """
    if not html_content:
        raise EmailParseError("HTML content cannot be empty")

    email_type = detect_email_type(html_content, subject)
    logger.info(f"Detected email type: {email_type}")

    if email_type in ("sinpe_debit", "sinpe_credit"):
        result = _parse_sinpe_email(html_content, email_type)
    else:
        result = _parse_card_email(html_content)

    if result:
        logger.info(f"Successfully parsed {email_type} transaction: {result.get('detalle', 'Unknown')}")
        return result

    raise EmailParseError(f"Could not extract transaction data from {email_type} email")


def _parse_sinpe_email(html_content: str, email_type: str) -> Optional[Dict[str, str]]:
    """
    Parse SINPE mobile transaction email.

    Args:
        html_content: HTML content of the email
        email_type: "sinpe_debit" or "sinpe_credit"

    Returns:
        Unified transaction dictionary or None
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    text = _clean_text(text)

    # Extract reference number
    ref_match = re.search(r'N[úu]mero de referencia:\s*(\d+)', text)
    referencia = ref_match.group(1) if ref_match else ""

    # Extract client name (Destino for debit, origen for credit)
    # Pattern stops before known field labels or end markers
    if email_type == "sinpe_debit":
        client_match = re.search(
            r'Nombre cliente Destino:\s*(.+?)(?=\s*(?:Entidad|Tel[eé]fono|Monto|Motivo|$))',
            text, re.IGNORECASE
        )
    else:
        client_match = re.search(
            r'Nombre cliente origen:\s*(.+?)(?=\s*(?:Entidad|Tel[eé]fono|Monto|Motivo|$))',
            text, re.IGNORECASE
        )

    cliente = _clean_text(client_match.group(1)) if client_match else ""

    # Extract amount - stops at next field or whitespace
    monto_match = re.search(r'Monto:\s*([\d,]+\.?\d*)', text)
    monto = monto_match.group(1) if monto_match else "0"

    # Extract motivo - stops before "Esta transacción" or end
    motivo_match = re.search(
        r'Motivo:\s*(.+?)(?=\s*Esta transacci[óo]n|$)',
        text, re.IGNORECASE
    )
    motivo = _clean_text(motivo_match.group(1)) if motivo_match else ""

    # Extract date and time
    # Pattern: "Esta transacción fue realizada el DD/MM/YYYY a las H:MM PM"
    date_match = re.search(
        r'Esta transacci[óo]n fue realizada el\s*(\d{1,2}/\d{2}/\d{4})\s*a las\s*(\d{1,2}:\d{2})\s*(AM|PM)?',
        text, re.IGNORECASE
    )

    if date_match:
        date_part = date_match.group(1)
        time_part = date_match.group(2)
        ampm = date_match.group(3) or ""

        # Convert to 24-hour format if needed
        if ampm:
            hour, minute = map(int, time_part.split(':'))
            if ampm.upper() == 'PM' and hour != 12:
                hour += 12
            elif ampm.upper() == 'AM' and hour == 12:
                hour = 0
            time_part = f"{hour:02d}:{minute:02d}:00"
        else:
            time_part = f"{time_part}:00"

        dia = f"{date_part} {time_part}"
    else:
        dia = ""

    # Build valor (negative for debit, positive for credit)
    if email_type == "sinpe_debit":
        valor = f"-{monto}"
    else:
        valor = monto

    # Build detalle: "Cliente / Motivo"
    if motivo:
        detalle = f"{cliente} / {motivo}"
    else:
        detalle = cliente

    # concepto_source is the motivo (for AI categorization)
    concepto_source = motivo

    return {
        "type": email_type,
        "dia": dia,
        "valor": valor,
        "concepto_source": concepto_source,
        "detalle": detalle,
        "referencia": referencia,
        "moneda": "COLON COSTA RICA",  # SINPE is always in colones
        "tarjeta": "SINPEMOVIL"  # SINPE mobile transaction identifier
    }


def _parse_card_email(html_content: str) -> Optional[Dict[str, str]]:
    """
    Parse card transaction email (original BCR format).

    Args:
        html_content: HTML content of the email

    Returns:
        Unified transaction dictionary or None

    Raises:
        DeniedTransactionError: If the transaction was denied
    """
    # Try parsing with BeautifulSoup first (HTML table format)
    # DeniedTransactionError will propagate up (don't fall back for denied transactions)
    result = _parse_card_from_html(html_content)

    if not result:
        # Fallback to plain text parsing only if HTML parsing failed (not for denied)
        result = _parse_card_from_plain_text(html_content)

    return result


def _parse_card_from_html(html_content: str) -> Optional[Dict[str, str]]:
    """
    Parse card transaction data from HTML table structure.

    Args:
        html_content: HTML string to parse

    Returns:
        Unified transaction dictionary or None
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract last 4 digits of card number from pattern like "****-****-****-9282"
    tarjeta = ""
    card_match = re.search(r'\*{4}-\*{4}-\*{4}-(\d{4})', html_content)
    if card_match:
        tarjeta = card_match.group(1)

    # Find all tbody sections
    tbodies = soup.find_all('tbody')

    for tbody in tbodies:
        # Extract all td elements
        tds = tbody.find_all('td')

        values = []
        for td in tds:
            text = td.get_text()
            text = _clean_text(text)
            if text:
                values.append(text)

        # Check if we have exactly 7 fields (BCR card transaction format)
        # Fields: Fecha, Autorización, No.Referencia, Monto, Moneda, Comercio, Estado
        if len(values) >= 7:
            date_str = values[0]  # DD/MM/YYYY HH:MM:SS
            reference = values[2]
            amount = values[3]
            moneda = values[4]  # e.g., "COLON COSTA RICA", "US DOLLAR"
            merchant = values[5]
            estado = values[6]  # Transaction status

            # Skip denied transactions (Estado: Negada)
            if estado.lower() == "negada":
                logger.info(f"Skipping denied card transaction: {merchant}, amount: {amount}")
                raise DeniedTransactionError(f"Transaction denied: {merchant}")

            # Card transactions are always negative (money out)
            valor = f"-{amount}"

            return {
                "type": "card",
                "dia": date_str,
                "valor": valor,
                "concepto_source": merchant,  # For AI categorization
                "detalle": merchant,
                "referencia": reference,
                "moneda": moneda,
                "tarjeta": tarjeta
            }

    return None


def _parse_card_from_plain_text(html_content: str) -> Optional[Dict[str, str]]:
    """
    Fallback parser for card transactions using regex on plain text.

    Args:
        html_content: HTML string to parse

    Returns:
        Unified transaction dictionary or None
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    text = _clean_text(text)

    # Skip denied transactions
    if re.search(r'\bNegada\b', text, re.IGNORECASE):
        logger.info("Skipping denied card transaction (detected in plain text)")
        raise DeniedTransactionError("Transaction denied (detected in plain text)")

    # Extract last 4 digits of card number from pattern like "****-****-****-9282"
    tarjeta = ""
    card_match = re.search(r'\*{4}-\*{4}-\*{4}-(\d{4})', html_content)
    if card_match:
        tarjeta = card_match.group(1)

    # Try to find date pattern: DD/MM/YYYY HH:MM:SS
    date_pattern = r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})'
    date_match = re.search(date_pattern, text)

    if not date_match:
        logger.warning("Could not find date pattern in email text")
        return None

    date_value = date_match.group(1)

    # Amount pattern
    amount_pattern = r'(\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?)'
    amount_matches = re.findall(amount_pattern, text)

    # Reference patterns (6-8 digit numbers)
    ref_pattern = r'\b(\d{6,8})\b'
    ref_matches = re.findall(ref_pattern, text)

    amount = amount_matches[0] if amount_matches else "0"
    reference = ref_matches[1] if len(ref_matches) > 1 else (ref_matches[0] if ref_matches else "")

    return {
        "type": "card",
        "dia": date_value,
        "valor": f"-{amount}",
        "concepto_source": "",
        "detalle": "",
        "referencia": reference,
        "moneda": "",  # Not reliably available in plain text fallback
        "tarjeta": tarjeta
    }


def _clean_text(text: str) -> str:
    """
    Clean and normalize text extracted from HTML.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text string
    """
    if not text:
        return ""

    # Replace non-breaking spaces
    text = text.replace('\xa0', ' ')
    text = text.replace('&nbsp;', ' ')

    # Normalize whitespace (multiple spaces to single)
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def validate_transaction_data(data: Dict[str, str]) -> bool:
    """
    Validate that transaction data contains required fields.

    Args:
        data: Transaction dictionary to validate

    Returns:
        True if all required fields are present and valid
    """
    required_fields = ['type', 'dia', 'valor', 'referencia']

    # Check required fields exist and are non-empty
    if not all(field in data and data[field] for field in required_fields):
        missing = [f for f in required_fields if f not in data or not data[f]]
        logger.error(f"Missing required fields in transaction data: {missing}")
        return False

    # Validate date format (should start with DD/MM/YYYY)
    date_pattern = r'\d{2}/\d{2}/\d{4}'
    if not re.match(date_pattern, data['dia']):
        logger.warning(f"Invalid date format: {data['dia']}")
        return False

    # Validate valor (should be numeric after removing formatting and sign)
    try:
        valor_clean = data['valor'].replace(',', '').replace(' ', '').replace('-', '')
        float(valor_clean)
    except ValueError:
        logger.warning(f"Invalid valor format: {data['valor']}")
        return False

    return True
