"""
BCR Bank Email to Google Sheets - Main Orchestrator

This script coordinates all components to:
1. Check Gmail for new BCR transaction emails (card and SINPE)
2. Parse transaction data from email HTML
3. Categorize transactions using Gemini AI
4. Append data to Google Sheets
5. Mark processed emails as read

Supported email types:
- Card transactions: "Notificación de Transacciones BCR"
- SINPE debit: "SINPEMOVIL - Notificación de transacción realizada" (debitado)
- SINPE credit: "SINPEMOVIL - Notificación de transacción realizada" (acreditado)

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
from src.email_parser import parse_bcr_email, EmailParseError, DeniedTransactionError
from src.ai_categorizer import categorize_merchant, batch_categorize
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
    subject = email.get('subject', '')

    try:
        # Step 1: Parse email HTML
        transaction = parse_bcr_email(email['html'], subject)
        detalle = transaction.get('detalle', 'Unknown')
        concepto_source = transaction.get('concepto_source', '')
        logger.info(f"  Parsed: {detalle}")

        # Step 2: Categorize transaction
        category = categorize_merchant(concepto_source)
        logger.info(f"  Category: {category}")

        # Step 3: Write to Sheets
        success, row_num = writer.append_transaction(transaction, category)

        if success:
            logger.info(f"  Written to row {row_num}")

            # Step 4: Mark email as read
            gmail.mark_as_read(email_id)

            return True, f"Processed: {detalle} -> {category}"
        else:
            return False, f"Failed to write to Sheets: {detalle}"

    except DeniedTransactionError as e:
        logger.info(f"  Skipped (denied): {e}")
        gmail.mark_as_read(email_id)
        return True, f"Skipped (denied): {e}"

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

        # Phase 1: Parse all emails first
        logger.info("Parsing all emails...")
        parsed_emails = []
        parse_errors = []

        for i, email in enumerate(emails, start=1):
            email_id = email.get('id', 'unknown')
            subject = email.get('subject', '')
            try:
                transaction = parse_bcr_email(email['html'], subject)
                parsed_emails.append((email, transaction))
                tx_type = transaction.get('type', 'unknown')
                detalle = transaction.get('detalle', 'Unknown')
                logger.info(f"  [{i}/{len(emails)}] Parsed ({tx_type}): {detalle}")
            except DeniedTransactionError as e:
                # Denied transactions should be marked as read but not processed
                logger.info(f"  [{i}/{len(emails)}] Skipped (denied): {e}")
                gmail.mark_as_read(email_id)
            except EmailParseError as e:
                parse_errors.append((email_id, str(e)))
                logger.error(f"  [{i}/{len(emails)}] Parse error: {e}")

        # Phase 2: Batch categorize all transactions (single API call)
        # Uses concepto_source: merchant name for cards, motivo for SINPE
        categories = {}
        if parsed_emails:
            concepto_sources = [t.get('concepto_source', '') for _, t in parsed_emails]
            logger.info(f"Batch categorizing {len(concepto_sources)} transaction(s)...")
            categories = batch_categorize(concepto_sources)

        # Phase 3: Write to sheets and mark as read
        logger.info("Writing to sheets...")
        processed = 0
        errors = len(parse_errors)
        results: List[str] = []

        for email, transaction in parsed_emails:
            email_id = email.get('id', 'unknown')
            concepto_source = transaction.get('concepto_source', '')
            detalle = transaction.get('detalle', 'Unknown')
            tx_type = transaction.get('type', 'unknown')
            category = categories.get(concepto_source, 'Uncategorized')

            try:
                success, row_num = writer.append_transaction(transaction, category)
                if success:
                    logger.info(f"  Written to row {row_num}: {detalle} -> {category}")
                    gmail.mark_as_read(email_id)
                    processed += 1
                    results.append(f"[OK] {tx_type}: {detalle} -> {category}")
                else:
                    errors += 1
                    results.append(f"[ERROR] Failed to write: {detalle}")
            except Exception as e:
                errors += 1
                results.append(f"[ERROR] {detalle}: {e}")
                logger.error(f"  Error writing {detalle}: {e}")

        # Add parse errors to results
        for email_id, error_msg in parse_errors:
            results.append(f"[ERROR] Parse failed ({email_id}): {error_msg}")

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
