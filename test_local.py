"""
Local Testing Script for BCR Email Sync

This script allows testing individual components before deployment.
Run each test function to verify your setup is working correctly.

Usage:
    python test_local.py

Before running:
    - Set environment variables or create a .env file
    - Ensure you have valid credentials
"""

import os
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def load_env_from_file():
    """Load environment variables from .env file and token.json."""
    # Load from .env file first
    env_file = Path('.env')
    if env_file.exists():
        print("Loading environment from .env file...")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Environment loaded from .env")

    # Also load from token.json if it exists (for GOOGLE_TOKEN)
    token_file = Path('token.json')
    if token_file.exists():
        print("Loading GOOGLE_TOKEN from token.json...")
        with open(token_file) as f:
            os.environ['GOOGLE_TOKEN'] = f.read()
        print("Token loaded")


def test_email_parser():
    """Test the email parser with a real BCR email sample."""
    print("\n" + "=" * 50)
    print("TEST: Email Parser")
    print("=" * 50)

    from src.email_parser import parse_bcr_email, EmailParseError

    # Real BCR email HTML structure
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>SOMOS EL BANCO DE COSTA RICA</title></head>
    <body>
        <div class="cuadro">
            <div class="azul">Transacciones en su tarjeta BCR: ****-****-****-8906</div>
            <div class="azul"> Detalle de Transacciones </div>
            <div>
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
            </div>
        </div>
    </body>
    </html>
    """

    try:
        result = parse_bcr_email(sample_html)
        print("\nParsed transaction data:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print("\n[PASS] Email parser working correctly")
        return True
    except EmailParseError as e:
        print(f"\n[FAIL] Parse error: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        return False


def test_categorizer():
    """Test the AI categorizer."""
    print("\n" + "=" * 50)
    print("TEST: AI Categorizer")
    print("=" * 50)

    if not os.environ.get('GEMINI_API_KEY'):
        print("\n[SKIP] GEMINI_API_KEY not set")
        return None

    from src.ai_categorizer import categorize_merchant

    test_merchants = [
        "MAS X MENOS DESAMPARADOS",
        "SERVICENTRO OCHOMOGO",
        "UBER TRIP",
        "RANDOM STORE XYZ"
    ]

    print("\nCategorizing test merchants:")
    all_passed = True

    for merchant in test_merchants:
        try:
            category = categorize_merchant(merchant)
            print(f"  {merchant} -> {category}")
        except Exception as e:
            print(f"  {merchant} -> ERROR: {e}")
            all_passed = False

    if all_passed:
        print("\n[PASS] Categorizer working correctly")
    else:
        print("\n[FAIL] Some categorizations failed")

    return all_passed


def test_sheets_connection():
    """Test Google Sheets connection."""
    print("\n" + "=" * 50)
    print("TEST: Google Sheets Connection")
    print("=" * 50)

    if not os.environ.get('GOOGLE_TOKEN'):
        print("\n[SKIP] GOOGLE_TOKEN not set")
        return None

    if not os.environ.get('SPREADSHEET_ID'):
        print("\n[SKIP] SPREADSHEET_ID not set")
        return None

    from src.sheets_writer import SheetsWriter

    try:
        writer = SheetsWriter()
        if writer.verify_connection():
            print("\n[PASS] Successfully connected to Google Sheets")
            return True
        else:
            print("\n[FAIL] Could not verify connection")
            return False
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False


def test_gmail_connection():
    """Test Gmail connection."""
    print("\n" + "=" * 50)
    print("TEST: Gmail Connection")
    print("=" * 50)

    if not os.environ.get('GOOGLE_TOKEN'):
        print("\n[SKIP] GOOGLE_TOKEN not set")
        return None

    from src.gmail_checker import GmailChecker

    try:
        checker = GmailChecker()
        count = checker.get_email_count()
        print(f"\nFound {count} unread BCR transaction email(s)")
        print("\n[PASS] Successfully connected to Gmail")
        return True
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False


def test_full_pipeline():
    """Test the full pipeline (without writing to sheets)."""
    print("\n" + "=" * 50)
    print("TEST: Full Pipeline (Dry Run)")
    print("=" * 50)

    required_vars = ['GOOGLE_TOKEN', 'GEMINI_API_KEY', 'SPREADSHEET_ID']
    missing = [v for v in required_vars if not os.environ.get(v)]

    if missing:
        print(f"\n[SKIP] Missing: {', '.join(missing)}")
        return None

    from src.gmail_checker import GmailChecker
    from src.email_parser import parse_bcr_email
    from src.ai_categorizer import categorize_merchant

    try:
        # Step 1: Check Gmail
        print("\n1. Checking Gmail...")
        checker = GmailChecker()
        emails = checker.check_new_emails()

        if not emails:
            print("   No emails to process")
            print("\n[PASS] Pipeline working (no emails to test)")
            return True

        print(f"   Found {len(emails)} email(s)")

        # Step 2: Parse first email
        print("\n2. Parsing first email...")
        email = emails[0]
        transaction = parse_bcr_email(email['html'])
        print(f"   Merchant: {transaction['merchant']}")
        print(f"   Amount: {transaction['amount']}")

        # Step 3: Categorize
        print("\n3. Categorizing...")
        category = categorize_merchant(transaction['merchant'])
        print(f"   Category: {category}")

        print("\n[PASS] Full pipeline working correctly")
        print("(Note: Did not write to Sheets in dry run)")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("BCR Email Sync - Local Test Suite")
    print("=" * 50)

    # Load environment
    load_env_from_file()

    # Run tests
    results = {
        "Email Parser": test_email_parser(),
        "AI Categorizer": test_categorizer(),
        "Sheets Connection": test_sheets_connection(),
        "Gmail Connection": test_gmail_connection(),
        "Full Pipeline": test_full_pipeline(),
    }

    # Print summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)

    for test_name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"
        print(f"  {status} {test_name}")

    print("=" * 50)

    # Return appropriate exit code
    if any(r is False for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
