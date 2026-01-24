"""
Email parser for BCR bank transaction notifications.

This module extracts structured transaction data from BCR email HTML
using BeautifulSoup for robust parsing.
"""

import re
import logging
from typing import Dict, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EmailParseError(Exception):
    """Error raised when email parsing fails."""
    pass


def parse_bcr_email(html_content: str) -> Dict[str, str]:
    """
    Extract structured transaction data from BCR email HTML.

    Args:
        html_content: Complete HTML string from email

    Returns:
        Dictionary with fields:
        {
            "date": "22/01/2024 14:30:45",
            "authorization": "123456",
            "reference": "789012",
            "amount": "15000.00",
            "currency": "CRC",
            "merchant": "MAS X MENOS DESAMPARADOS",
            "status": "Approved"
        }

    Raises:
        EmailParseError: If email cannot be parsed
    """
    if not html_content:
        raise EmailParseError("HTML content cannot be empty")

    # Try parsing with BeautifulSoup first
    result = _parse_from_html(html_content)

    if result:
        logger.info(f"Successfully parsed transaction: {result.get('merchant', 'Unknown')}")
        return result

    # Fallback to plain text parsing
    result = _parse_from_plain_text(html_content)

    if result:
        logger.info(f"Parsed from plain text: {result.get('merchant', 'Unknown')}")
        return result

    raise EmailParseError("Could not extract transaction data from email")


def _parse_from_html(html_content: str) -> Optional[Dict[str, str]]:
    """
    Parse transaction data from HTML structure.

    Looks for tbody elements with exactly 7 td values which correspond
    to BCR transaction fields.

    Args:
        html_content: HTML string to parse

    Returns:
        Transaction dictionary or None if parsing fails
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all tbody sections
    tbodies = soup.find_all('tbody')

    for tbody in tbodies:
        # Extract all td elements
        tds = tbody.find_all('td')

        values = []
        for td in tds:
            # Clean text content
            text = td.get_text()
            text = _clean_text(text)

            if text:
                values.append(text)

        # Check if we have exactly 7 fields (BCR transaction format)
        if len(values) >= 7:
            return {
                "date": values[0],
                "authorization": values[1],
                "reference": values[2],
                "amount": values[3],
                "currency": values[4],
                "merchant": values[5],
                "status": values[6]
            }

    return None


def _parse_from_plain_text(html_content: str) -> Optional[Dict[str, str]]:
    """
    Fallback parser using regex on plain text.

    Used when HTML structure doesn't match expected format.

    Args:
        html_content: HTML string to parse

    Returns:
        Transaction dictionary or None if parsing fails
    """
    # Strip HTML tags for plain text parsing
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    text = _clean_text(text)

    # Try to find date pattern: DD/MM/YYYY HH:MM:SS
    date_pattern = r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})'
    date_match = re.search(date_pattern, text)

    if not date_match:
        logger.warning("Could not find date pattern in email text")
        return None

    date_value = date_match.group(1)

    # Try to extract other fields using common patterns
    # Amount pattern: numbers with optional decimals
    amount_pattern = r'(\d{1,3}(?:[,.\s]?\d{3})*(?:[.,]\d{2})?)'
    amount_matches = re.findall(amount_pattern, text)

    # Currency pattern
    currency_pattern = r'(CRC|USD|EUR)'
    currency_match = re.search(currency_pattern, text, re.IGNORECASE)

    # Authorization/Reference patterns (6-digit numbers)
    ref_pattern = r'\b(\d{6})\b'
    ref_matches = re.findall(ref_pattern, text)

    # Build result with available data
    result = {
        "date": date_value,
        "authorization": ref_matches[0] if len(ref_matches) > 0 else "",
        "reference": ref_matches[1] if len(ref_matches) > 1 else "",
        "amount": amount_matches[0] if amount_matches else "",
        "currency": currency_match.group(1) if currency_match else "CRC",
        "merchant": "",
        "status": "Unknown"
    }

    # Try to find merchant name (usually after currency or before status)
    # This is a heuristic and may need adjustment based on actual email format
    status_keywords = ["approved", "aprobad", "rejected", "rechazad", "pending"]
    for keyword in status_keywords:
        if keyword.lower() in text.lower():
            result["status"] = "Approved" if "aprobad" in keyword.lower() or "approved" in keyword.lower() else "Rejected"
            break

    return result if result["date"] else None


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
    required_fields = ['date', 'amount', 'merchant', 'status']

    # Check required fields exist and are non-empty
    if not all(field in data and data[field] for field in required_fields):
        logger.error("Missing required fields in transaction data")
        return False

    # Validate date format
    date_pattern = r'\d{2}/\d{2}/\d{4}'
    if not re.match(date_pattern, data['date']):
        logger.warning(f"Invalid date format: {data['date']}")
        return False

    # Validate amount (should be numeric after removing formatting)
    try:
        amount_clean = data['amount'].replace(',', '').replace(' ', '')
        float(amount_clean)
    except ValueError:
        logger.warning(f"Invalid amount format: {data['amount']}")
        return False

    return True
