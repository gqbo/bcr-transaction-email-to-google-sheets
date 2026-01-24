"""
BCR Bank Email to Google Sheets - Main Orchestrator

This script coordinates all components to:
1. Check Gmail for new BCR transaction emails
2. Parse transaction data from email HTML
3. Categorize merchants using Gemini AI
4. Append data to Google Sheets
5. Mark processed emails as read

Designed to run hourly via GitHub Actions.
"""

import os
import sys
import logging
from typing import List, Tuple
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
# In GitHub Actions, env vars are set directly via secrets
load_dotenv()

from src.gmail_checker import GmailChecker
from src.email_parser import parse_bcr_email, EmailParseError
from src.ai_categorizer import categorize_merchant
from src.sheets_writer import SheetsWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def validate_environment() -> bool:
    """
    Validate all required environment variables are present.

    Returns:
        True if all variables are set
    """
    required_vars = [
        'GOOGLE_TOKEN',
        'GEMINI_API_KEY',
        'SPREADSHEET_ID'
    ]

    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)

    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return False

    logger.info("All required environment variables present")
    return True


def process_email(
    email: dict,
    writer: SheetsWriter,
    gmail: GmailChecker
) -> Tuple[bool, str]:
    """
    Process a single email through the full pipeline.

    Args:
        email: Email dictionary from Gmail checker
        writer: SheetsWriter instance
        gmail: GmailChecker instance for marking as read

    Returns:
        Tuple of (success: bool, message: str)
    """
    email_id = email.get('id', 'unknown')

    try:
        # Step 1: Parse email HTML
        transaction = parse_bcr_email(email['html'])
        merchant = transaction.get('merchant', 'Unknown')
        logger.info(f"  Parsed: {merchant}")

        # Step 2: Categorize merchant
        category = categorize_merchant(merchant)
        logger.info(f"  Category: {category}")

        # Step 3: Write to Sheets
        success, row_num = writer.append_transaction(transaction, category)

        if success:
            logger.info(f"  Written to row {row_num}")

            # Step 4: Mark email as read
            gmail.mark_as_read(email_id)

            return True, f"Processed: {merchant} -> {category}"
        else:
            return False, f"Failed to write to Sheets: {merchant}"

    except EmailParseError as e:
        logger.error(f"  Parse error: {e}")
        return False, f"Parse error: {e}"

    except Exception as e:
        logger.error(f"  Unexpected error: {e}")
        return False, f"Error: {e}"


def main():
    """
    Main entry point for the BCR email sync process.

    Orchestrates the full pipeline:
    Gmail -> Parse -> Categorize -> Sheets -> Mark Read
    """
    logger.info("=" * 50)
    logger.info("BCR Bank Email Sync - Starting")
    logger.info("=" * 50)

    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        sys.exit(1)

    try:
        # Initialize components
        logger.info("Initializing components...")
        gmail = GmailChecker()
        writer = SheetsWriter()

        # Verify Sheets connection
        if not writer.verify_connection():
            logger.error("Failed to connect to Google Sheets. Exiting.")
            sys.exit(1)

        # Check for new emails
        logger.info("Checking for new emails...")
        emails = gmail.check_new_emails()

        if not emails:
            logger.info("No new BCR transaction emails found.")
            logger.info("=" * 50)
            logger.info("Sync complete - Nothing to process")
            logger.info("=" * 50)
            sys.exit(0)

        logger.info(f"Found {len(emails)} email(s) to process")
        logger.info("-" * 50)

        # Process each email
        processed = 0
        errors = 0
        results: List[str] = []

        for i, email in enumerate(emails, start=1):
            logger.info(f"Processing email {i}/{len(emails)}...")

            success, message = process_email(email, writer, gmail)

            if success:
                processed += 1
                results.append(f"[OK] {message}")
            else:
                errors += 1
                results.append(f"[ERROR] {message}")

            logger.info("-" * 30)

        # Print summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total emails:     {len(emails)}")
        logger.info(f"Processed:        {processed}")
        logger.info(f"Errors:           {errors}")
        logger.info("-" * 50)

        for result in results:
            logger.info(result)

        logger.info("=" * 50)
        logger.info("Sync complete")
        logger.info("=" * 50)

        # Exit with error if any emails failed
        if errors > 0:
            sys.exit(1)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
