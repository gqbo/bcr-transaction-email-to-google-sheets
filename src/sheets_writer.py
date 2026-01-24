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
        self.sheet_range = 'A:E'  # Columns A through E (Fecha, No.Referencia, Monto, Comercio, Categoria)

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

    def append_transaction(
        self,
        transaction: Dict[str, str],
        category: str
    ) -> Tuple[bool, Optional[int]]:
        """
        Append a transaction row to Google Sheets.

        Args:
            transaction: Transaction dictionary from email parser
            category: Category from AI categorizer

        Returns:
            Tuple of (success: bool, row_number: Optional[int])
        """
        # Build row data matching column order:
        # Fecha | No.Referencia | Monto | Comercio | Categoria
        row = [
            transaction.get('date', ''),       # Fecha
            transaction.get('reference', ''),  # No.Referencia
            transaction.get('amount', ''),     # Monto
            transaction.get('merchant', ''),   # Comercio
            category                           # Categoria
        ]

        return self._append_row(row)

    def _append_row(self, row: List[str]) -> Tuple[bool, Optional[int]]:
        """
        Append a single row to the sheet with retry logic.

        Args:
            row: List of values to append

        Returns:
            Tuple of (success: bool, row_number: Optional[int])
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                body = {'values': [row]}

                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=self.sheet_range,
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
