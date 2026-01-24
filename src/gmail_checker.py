"""
Gmail checker for BCR bank transaction emails.

This module monitors Gmail for unread BCR transaction notification
emails and extracts their content for processing.
"""

import os
import json
import base64
import logging
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Search query for BCR transaction emails (card transactions and SINPE)
BCR_SEARCH_QUERY = '(subject:"Notificación de Transacciones BCR" OR subject:"SINPEMOVIL - Notificación de transacción realizada") is:unread'


class GmailChecker:
    """
    Gmail checker for monitoring BCR transaction emails.

    Connects to Gmail API, searches for unread BCR notifications,
    and extracts email content for processing.
    """

    def __init__(self):
        """
        Initialize the Gmail checker.

        Loads credentials from environment variables and builds
        the Gmail API service.

        Raises:
            ValueError: If required environment variables are missing
        """
        self.service = self._build_service()
        self.search_query = BCR_SEARCH_QUERY

    def _build_service(self):
        """
        Build the Gmail API service.

        Returns:
            Gmail API service instance

        Raises:
            ValueError: If credentials are missing or invalid
        """
        token_json = os.environ.get('GOOGLE_TOKEN')
        if not token_json:
            raise ValueError("GOOGLE_TOKEN environment variable is not set")

        try:
            token_info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_info)

            service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully connected to Gmail API")
            return service

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in GOOGLE_TOKEN: {e}")
        except Exception as e:
            raise ValueError(f"Failed to build Gmail service: {e}")

    def check_new_emails(self) -> List[Dict[str, str]]:
        """
        Check for new unread BCR transaction emails.

        Returns:
            List of email dictionaries with fields:
            {
                "id": "message_id",
                "subject": "email subject",
                "html": "html body content"
            }
        """
        try:
            # Search for emails matching query
            results = self.service.users().messages().list(
                userId='me',
                q=self.search_query
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                logger.info("No new BCR transaction emails found")
                return []

            logger.info(f"Found {len(messages)} new email(s)")

            # Get full content for each email
            emails = []
            for msg in messages:
                email_data = self._get_email_content(msg['id'])
                if email_data:
                    emails.append(email_data)

            return emails

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error checking emails: {e}")
            return []

    def _get_email_content(self, message_id: str) -> Optional[Dict[str, str]]:
        """
        Get the full content of an email by ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Email dictionary or None if extraction fails
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            subject = self._get_subject(message)
            html_body = self._get_html_body(message)

            if not html_body:
                logger.warning(f"No HTML body found for email {message_id}")
                return None

            return {
                "id": message_id,
                "subject": subject,
                "html": html_body
            }

        except HttpError as e:
            logger.error(f"Failed to get email {message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing email {message_id}: {e}")
            return None

    def _get_subject(self, message: dict) -> str:
        """
        Extract subject from email message.

        Args:
            message: Gmail message object

        Returns:
            Email subject string
        """
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header.get('name', '').lower() == 'subject':
                return header.get('value', '')
        return ''

    def _get_html_body(self, message: dict) -> Optional[str]:
        """
        Extract HTML body from email message.

        Handles both simple and multipart MIME structures.

        Args:
            message: Gmail message object

        Returns:
            HTML body string or None
        """
        payload = message.get('payload', {})

        # Try to get body directly (simple message)
        body_data = payload.get('body', {}).get('data')
        if body_data:
            return self._decode_body(body_data)

        # Handle multipart messages
        parts = payload.get('parts', [])
        return self._find_html_part(parts)

    def _find_html_part(self, parts: list) -> Optional[str]:
        """
        Recursively find HTML part in multipart message.

        Args:
            parts: List of MIME parts

        Returns:
            HTML content or None
        """
        for part in parts:
            mime_type = part.get('mimeType', '')

            # Check if this is the HTML part
            if mime_type == 'text/html':
                body_data = part.get('body', {}).get('data')
                if body_data:
                    return self._decode_body(body_data)

            # Recursively check nested parts
            nested_parts = part.get('parts', [])
            if nested_parts:
                result = self._find_html_part(nested_parts)
                if result:
                    return result

        return None

    def _decode_body(self, encoded_body: str) -> str:
        """
        Decode base64 URL-safe encoded email body.

        Args:
            encoded_body: Base64 URL-safe encoded string

        Returns:
            Decoded string
        """
        try:
            decoded = base64.urlsafe_b64decode(encoded_body)
            return decoded.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decode email body: {e}")
            return ''

    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark an email as read by removing the UNREAD label.

        Args:
            message_id: Gmail message ID

        Returns:
            True if successful
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()

            logger.info(f"Marked email {message_id} as read")
            return True

        except HttpError as e:
            logger.error(f"Failed to mark email as read: {e}")
            return False
        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
            return False

    def get_email_count(self) -> int:
        """
        Get count of unread BCR emails without fetching content.

        Returns:
            Number of matching emails
        """
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=self.search_query
            ).execute()

            return len(results.get('messages', []))

        except Exception as e:
            logger.error(f"Error getting email count: {e}")
            return 0
