"""
Google Sheets writer for BCR transaction data.

This module handles writing transaction data to Google Sheets
using the Google Sheets API.
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Tuple

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Column headers for new sheets
HEADERS = ["Dia", "Valor", "Concepto", "Detalle", "Referencia", "Moneda", "Tarjeta"]


class SheetsWriter:
    """
    Google Sheets writer for appending transaction data.

    Handles authentication, connection, and row appending
    to a specified Google Sheet.
    """

    def __init__(self):
        """
        Initialize the Sheets writer.

        Loads credentials from environment variables and builds
        the Sheets API service.

        Raises:
            ValueError: If required environment variables are missing
        """
        self.spreadsheet_id = os.environ.get('SPREADSHEET_ID')
        if not self.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID environment variable is not set")

        self.service = self._build_service()
        self.sheet_range = 'A:G'  # Columns A through G (Dia, Valor, Concepto, Detalle, Referencia, Moneda, Tarjeta)
        self._cached_sheets: Optional[List[str]] = None  # Cache for existing sheet names

    def _build_service(self):
        """
        Build the Google Sheets API service.

        Returns:
            Google Sheets API service instance

        Raises:
            ValueError: If credentials are missing or invalid
        """
        # Load token from environment
        token_json = os.environ.get('GOOGLE_TOKEN')
        if not token_json:
            raise ValueError("GOOGLE_TOKEN environment variable is not set")

        try:
            token_info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_info)

            service = build('sheets', 'v4', credentials=creds)
            logger.info("Successfully connected to Google Sheets API")
            return service

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in GOOGLE_TOKEN: {e}")
        except Exception as e:
            raise ValueError(f"Failed to build Sheets service: {e}")

    def _get_sheet_name_from_date(self, date_str: str) -> str:
        """
        Extract MM/YYYY from a date string.

        Args:
            date_str: Date in format 'DD/MM/YYYY HH:MM:SS' (e.g., '16/01/2026 22:31:15')

        Returns:
            Sheet name in format 'MM/YYYY' (e.g., '01/2026')
        """
        # Date format is DD/MM/YYYY HH:MM:SS
        # Extract MM/YYYY from positions 3-5 (month) and 6-10 (year)
        parts = date_str.split('/')
        if len(parts) >= 3:
            month = parts[1]  # MM
            year = parts[2].split()[0]  # YYYY (remove time part)
            return f"{month}/{year}"
        # Fallback if format is unexpected
        logger.warning(f"Unexpected date format: {date_str}")
        return "Unknown"

    def _get_existing_sheets(self) -> List[str]:
        """
        Get list of all sheet names in the spreadsheet.

        Uses caching to avoid repeated API calls within the same session.

        Returns:
            List of sheet names
        """
        if self._cached_sheets is not None:
            return self._cached_sheets

        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                fields='sheets.properties.title'
            ).execute()

            sheets = result.get('sheets', [])
            self._cached_sheets = [
                sheet.get('properties', {}).get('title', '')
                for sheet in sheets
            ]
            logger.info(f"Found {len(self._cached_sheets)} existing sheets")
            return self._cached_sheets

        except HttpError as e:
            logger.error(f"Failed to get sheets list: {e}")
            return []

    def _create_sheet(self, sheet_name: str) -> bool:
        """
        Create a new sheet with headers at the beginning of the spreadsheet.

        Args:
            sheet_name: Name for the new sheet (e.g., '01/2026')

        Returns:
            True if sheet was created successfully
        """
        try:
            # Create the sheet at index 0 (first position)
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name,
                            'index': 0  # Add at the beginning
                        }
                    }
                }]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()

            logger.info(f"Created new sheet: {sheet_name}")

            # Add headers to the new sheet
            header_range = f"'{sheet_name}'!A1:G1"
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=header_range,
                valueInputOption='RAW',
                body={'values': [HEADERS]}
            ).execute()

            logger.info(f"Added headers to sheet: {sheet_name}")

            # Update cache
            if self._cached_sheets is not None:
                self._cached_sheets.insert(0, sheet_name)

            return True

        except HttpError as e:
            logger.error(f"Failed to create sheet '{sheet_name}': {e}")
            return False

    def _ensure_sheet_exists(self, sheet_name: str) -> bool:
        """
        Ensure a sheet exists, creating it if necessary.

        Args:
            sheet_name: Name of the sheet to check/create

        Returns:
            True if sheet exists or was created successfully
        """
        existing_sheets = self._get_existing_sheets()

        if sheet_name in existing_sheets:
            return True

        return self._create_sheet(sheet_name)

    def append_transaction(
        self,
        transaction: Dict[str, str],
        category: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Append a transaction row to Google Sheets.

        Automatically determines the correct sheet based on transaction date
        and creates the sheet if it doesn't exist.

        Args:
            transaction: Transaction dictionary from email parser with fields:
                - dia: Date and time (DD/MM/YYYY HH:MM:SS)
                - valor: Amount with sign (negative for expenses)
                - detalle: Merchant name or "Cliente / Motivo"
                - referencia: Reference number
            category: Category from AI categorizer (Concepto)

        Returns:
            Tuple of (success: bool, row_number: Optional[int])
        """
        # Determine sheet name from transaction date
        date_str = transaction.get('dia', '')
        sheet_name = self._get_sheet_name_from_date(date_str)

        # Ensure the sheet exists (creates with headers if not)
        if not self._ensure_sheet_exists(sheet_name):
            logger.error(f"Failed to ensure sheet '{sheet_name}' exists")
            return False, None

        # Build row data matching column order:
        # Dia | Valor | Concepto | Detalle | Referencia | Moneda | Tarjeta
        row = [
            date_str,                            # Dia
            transaction.get('valor', ''),        # Valor (with sign)
            category,                            # Concepto (AI category)
            transaction.get('detalle', ''),      # Detalle
            transaction.get('referencia', ''),   # Referencia
            transaction.get('moneda', ''),       # Moneda
            transaction.get('tarjeta', '')       # Tarjeta
        ]

        return self._append_row(row, sheet_name)

    def _append_row(self, row: List[str], sheet_name: str) -> Tuple[bool, Optional[int]]:
        """
        Append a single row to a specific sheet with retry logic.

        Args:
            row: List of values to append
            sheet_name: Name of the sheet to append to (e.g., '01/2026')

        Returns:
            Tuple of (success: bool, row_number: Optional[int])
        """
        # Build range with sheet name (e.g., '01/2026'!A:E)
        sheet_range = f"'{sheet_name}'!{self.sheet_range}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                body = {'values': [row]}

                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=sheet_range,
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()

                # Extract update info
                updates = result.get('updates', {})
                updated_rows = updates.get('updatedRows', 0)
                updated_range = updates.get('updatedRange', '')

                if updated_rows > 0:
                    # Extract row number from range (e.g., "Sheet1!A5:F5" -> 5)
                    row_number = self._extract_row_number(updated_range)
                    logger.info(
                        f"Successfully appended row {row_number}: "
                        f"{row[3]} - {row[4]}"  # merchant - category
                    )
                    return True, row_number

                logger.warning("Append succeeded but no rows reported as updated")
                return True, None

            except HttpError as e:
                status_code = e.resp.status
                if status_code == 403:
                    logger.error("Permission denied - check Sheet sharing settings")
                    return False, None
                elif status_code == 404:
                    logger.error(f"Spreadsheet not found: {self.spreadsheet_id}")
                    return False, None
                elif status_code == 429:
                    # Rate limit - wait and retry
                    logger.warning(f"Rate limited, attempt {attempt}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY * attempt)
                        continue
                else:
                    logger.error(f"HTTP error {status_code}: {e}")

                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                    continue
                return False, None

            except Exception as e:
                logger.error(f"Unexpected error appending row: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                    continue
                return False, None

        logger.error(f"All {MAX_RETRIES} attempts failed to append row")
        return False, None

    def _extract_row_number(self, range_str: str) -> Optional[int]:
        """
        Extract row number from a range string.

        Args:
            range_str: Range like "Sheet1!A5:F5"

        Returns:
            Row number or None
        """
        import re
        match = re.search(r'[A-Z]+(\d+)', range_str)
        if match:
            return int(match.group(1))
        return None

    def batch_append(
        self,
        transactions: List[Tuple[Dict[str, str], str]]
    ) -> Tuple[int, int]:
        """
        Append multiple transactions in batch.

        Args:
            transactions: List of (transaction, category) tuples

        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0

        for transaction, category in transactions:
            success, _ = self.append_transaction(transaction, category)
            if success:
                success_count += 1
            else:
                failure_count += 1

        logger.info(
            f"Batch append complete: {success_count} succeeded, "
            f"{failure_count} failed"
        )
        return success_count, failure_count

    def verify_connection(self) -> bool:
        """
        Verify connection to the spreadsheet.

        Returns:
            True if connection is valid
        """
        try:
            # Try to get spreadsheet metadata
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            title = result.get('properties', {}).get('title', 'Unknown')
            logger.info(f"Connected to spreadsheet: {title}")
            return True

        except HttpError as e:
            logger.error(f"Failed to verify connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error verifying connection: {e}")
            return False
