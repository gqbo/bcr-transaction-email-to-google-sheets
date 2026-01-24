# Python Best Practices Guide for BCR Email Project
## Based on Real Python Cheatsheet

---

## 🎯 GOLDEN RULES FROM CHEATSHEET

### 1. VARIABLES & NAMING (Page 1)
```python
# ✅ GOOD: Descriptive snake_case
email_html_content = get_email_body()
transaction_data = parse_email(email_html_content)
categorized_merchant = categorize(transaction_data['merchant'])

# ❌ BAD: Non-descriptive names
data = get()
x = parse(data)
y = cat(x['c'])
```

### 2. STRINGS (Page 1)

#### Use f-strings for formatting
```python
# ✅ GOOD: Modern f-string
merchant = "MAS X MENOS"
category = "Mercado"
logger.info(f"Categorizing '{merchant}' as '{category}'")

# ❌ BAD: String concatenation
logger.info("Categorizing '" + merchant + "' as '" + category + "'")
```

#### Useful string methods for this project
```python
# Clean data from email
raw_text = "  MAS X MENOS   "
clean = raw_text.strip()  # "MAS X MENOS"

# Replace problematic characters
html_text = "Amount:&nbsp;15000"
clean = html_text.replace("&nbsp;", " ")  # "Amount: 15000"

# Split into parts
merchant = "MAS X MENOS DESAMPARADOS"
words = merchant.split()  # ["MAS", "X", "MENOS", "DESAMPARADOS"]
```

---

## 3. FUNCTIONS (Page 2)

### Proper function structure
```python
def parse_bcr_email(html_content: str) -> dict:
    """
    Extract transaction data from BCR email HTML.
    
    Args:
        html_content: Complete HTML string from email
        
    Returns:
        dict: Transaction dictionary with fields
        {
            "date": "22/01/2024 14:30:45",
            "merchant": "MAS X MENOS",
            "amount": "15000.00",
            ...
        }
        
    Raises:
        ValueError: If email cannot be parsed
    """
    # Validate input
    if not html_content:
        raise ValueError("HTML content cannot be empty")
    
    # Parsing logic...
    transaction_data = extract_transaction(html_content)
    
    # Validate output
    if not transaction_data:
        raise ValueError("Could not extract transaction data")
    
    return transaction_data
```

### Parameters with defaults
```python
# ✅ GOOD: Default values for optional parameters
def categorize_merchant(merchant: str, use_cache: bool = True) -> str:
    if use_cache:
        cached = get_from_cache(merchant)
        if cached:
            return cached
    
    category = call_gemini_api(merchant)
    return category

# Usage
cat1 = categorize_merchant("MAS X MENOS")  # uses cache by default
cat2 = categorize_merchant("MAS X MENOS", use_cache=False)  # forces new call
```

---

## 4. CONDITIONALS (Page 1)

### If-elif-else for business logic
```python
def validate_transaction_data(data: dict) -> bool:
    """Validate transaction data is correct."""
    
    # Check required fields
    required_fields = ['date', 'amount', 'merchant', 'status']
    
    if not all(field in data for field in required_fields):
        logger.error("Missing required fields in transaction")
        return False
    
    # Validate amount
    try:
        amount = float(data['amount'].replace(',', ''))
        if amount <= 0:
            logger.warning(f"Invalid amount: {amount}")
            return False
    except ValueError:
        logger.error(f"Amount is not a valid number: {data['amount']}")
        return False
    
    # Validate status
    valid_states = ['Approved', 'Rejected', 'Pending']
    if data['status'] not in valid_states:
        logger.warning(f"Invalid status: {data['status']}")
        return False
    
    return True
```

### Logical operators
```python
# ✅ GOOD: and, or, not
if email_found and is_unread and matches_subject:
    process_email()

if is_error or is_timeout:
    retry_operation()

if not already_processed:
    mark_as_processed()
```

---

## 5. LOOPS (Page 2)

### For loop with enumerate for indices
```python
# ✅ GOOD: enumerate when you need the index
emails = get_new_emails()

for i, email in enumerate(emails, start=1):
    logger.info(f"Processing email {i}/{len(emails)}")
    try:
        process_email(email)
    except Exception as e:
        logger.error(f"Error in email {i}: {e}")
```

### While with break for retry logic
```python
def call_api_with_retry(url: str, max_attempts: int = 3) -> dict:
    """Call API with automatic retries."""
    attempt = 0
    
    while True:
        attempt += 1
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            if attempt >= max_attempts:
                logger.error(f"Failed after {max_attempts} attempts")
                raise
            
            logger.warning(f"Attempt {attempt} failed: {e}. Retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
```

---

## 6. COLLECTIONS (Page 3)

### Lists for transaction data
```python
# ✅ GOOD: List comprehensions to transform data
raw_values = ["  15000.00  ", "  MAS X MENOS  ", "  Approved  "]
clean_values = [value.strip() for value in raw_values]
# ["15000.00", "MAS X MENOS", "Approved"]

# Filter empty values
all_values = ["Date", "", "Amount", "", "Merchant"]
valid_values = [v for v in all_values if v]
# ["Date", "Amount", "Merchant"]
```

### Dictionaries for structured data
```python
# ✅ GOOD: Dictionaries for transactions
transaction = {
    "date": "22/01/2024 14:30:45",
    "authorization": "123456",
    "amount": "15000.00",
    "merchant": "MAS X MENOS"
}

# Safe access with get() and default
merchant = transaction.get("merchant", "UNKNOWN")
category = transaction.get("category", "Uncategorized")

# Iterate over items
for key, value in transaction.items():
    print(f"{key}: {value}")
```

### Sets for categorization keywords
```python
# ✅ GOOD: Sets for fast keyword lookup
GROCERY_KEYWORDS = {
    "MXM", "SUPER", "MAS X MENOS", 
    "PRICE SMART", "FRESK MARKET"
}

FUEL_KEYWORDS = {
    "SERVICENTRO", "ESTACION", "GAS STATION"
}

# Check if merchant contains keyword
def contains_keyword(merchant: str, keywords: set) -> bool:
    merchant_upper = merchant.upper()
    return any(keyword in merchant_upper for keyword in keywords)

# Usage
if contains_keyword("MAS X MENOS DESAMPARADOS", GROCERY_KEYWORDS):
    return "Mercado (alimentos, aseo hogar)"
```

---

## 7. EXCEPTIONS (Page 2)

### Try-Except-Finally for critical operations
```python
def write_to_sheets(data: dict) -> bool:
    """
    Write data to Google Sheets with robust error handling.
    """
    try:
        # Attempt write
        service = get_sheets_service()
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='A:H',
            body={'values': [[*data.values()]]},
            valueInputOption='RAW'
        ).execute()
        
        logger.info(f"Row added successfully: {result['updates']['updatedRows']}")
        return True
    
    except HttpError as e:
        if e.resp.status == 403:
            logger.error("No permission to write to Sheets")
        elif e.resp.status == 404:
            logger.error("Spreadsheet not found")
        else:
            logger.error(f"HTTP error writing: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error writing: {e}")
        return False
    
    finally:
        # Always execute (cleanup, logging, etc)
        logger.debug("Write operation finished")
```

### Raising custom exceptions
```python
class EmailParseError(Exception):
    """Error parsing BCR email."""
    pass

def parse_bcr_email(html: str) -> dict:
    if not html:
        raise EmailParseError("HTML is empty")
    
    data = extract_data(html)
    
    if not data:
        raise EmailParseError("Could not extract data from HTML")
    
    return data

# Usage
try:
    transaction = parse_bcr_email(email_html)
except EmailParseError as e:
    logger.error(f"Error parsing email: {e}")
    # Handle specifically this type of error
```

---

## 8. FILE I/O (Page 3)

### Logging to file
```python
import logging
from pathlib import Path

# Setup logging
def setup_logging():
    """Configure logging to file and console."""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler for file
    file_handler = logging.FileHandler('logs/processing.log')
    file_handler.setFormatter(formatter)
    
    # Handler for console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# In main.py
if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting email processing...")
```

### Read configuration files
```python
from pathlib import Path

# ✅ GOOD: Use pathlib for paths
def load_categories_config():
    """Load category configuration from file."""
    config_path = Path("config/categories.txt")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, mode="r", encoding="utf-8") as f:
        categories = [line.strip() for line in f if line.strip()]
    
    return categories
```

---

## 9. IMPORTS & MODULES (Page 3)

### Import organization
```python
# main.py

# 1. Standard library (alphabetical)
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 2. Third-party libraries (alphabetical)
import google.generativeai as genai
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 3. Local modules (alphabetical)
from config.categories import VALID_CATEGORIES
from src.ai_categorizer import categorize_merchant
from src.email_parser import parse_bcr_email
from src.gmail_checker import check_new_emails
from src.sheets_writer import append_to_sheet
```

### Relative imports in packages
```python
# src/email_parser.py
from .utils import clean_html, extract_table_data
from ..config.categories import VALID_CATEGORIES

# ❌ AVOID: import *
from utils import *  # Don't do this

# ✅ GOOD: Specific import
from utils import clean_html, extract_table_data
```

---

## 10. CLASSES (Page 2)

### When to use classes vs functions

**✅ Use classes when:**
- Need to maintain state
- Have multiple related methods
- Need multiple instances with different config

```python
# ✅ GOOD: Class to handle Gmail connection
class GmailChecker:
    """Monitor Gmail emails and process new ones."""
    
    def __init__(self, credentials_path: str, search_query: str):
        self.credentials_path = credentials_path
        self.search_query = search_query
        self.service = None
        self._connect()
    
    def _connect(self):
        """Connect to Gmail API."""
        creds = Credentials.from_authorized_user_file(self.credentials_path)
        self.service = build('gmail', 'v1', credentials=creds)
        logging.info("Connected to Gmail API")
    
    def check_new_emails(self) -> List[dict]:
        """Return list of new emails."""
        results = self.service.users().messages().list(
            userId='me',
            q=self.search_query
        ).execute()
        
        messages = results.get('messages', [])
        return [self.get_email_content(msg['id']) for msg in messages]
    
    def get_email_content(self, email_id: str) -> dict:
        """Get content of specific email."""
        message = self.service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        return {
            'id': email_id,
            'subject': self._get_subject(message),
            'html': self._get_html_body(message)
        }

# Usage
checker = GmailChecker(
    credentials_path="credentials/gmail.json",
    search_query='subject:"BCR Notification" is:unread'
)
emails = checker.check_new_emails()
```

**✅ Use functions when:**
- Simple, single operation
- No state needed
- Data transformation

```python
# ✅ GOOD: Simple function for parsing
def parse_bcr_email(html_content: str) -> dict:
    """Parse HTML and return structured data."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # ... parsing logic
    return transaction_data
```

---

## 11. COMPREHENSIONS (Page 3)

### List comprehensions for transformations
```python
# Clean list of values extracted from HTML
raw_values = ["  Date  ", "  Amount  ", "", "  Merchant  "]

# ✅ GOOD: Comprehension in one line
clean_values = [v.strip() for v in raw_values if v.strip()]
# ["Date", "Amount", "Merchant"]

# Equivalent with loop (more verbose)
clean_values = []
for v in raw_values:
    if v.strip():
        clean_values.append(v.strip())
```

### Dict comprehensions for mappings
```python
# Create dictionary of keywords → category
keywords_list = [
    ("MXM", "Grocery"),
    ("SUPER", "Grocery"),
    ("SERVICENTRO", "Fuel")
]

# ✅ GOOD: Dict comprehension
keyword_map = {kw: cat for kw, cat in keywords_list}
# {"MXM": "Grocery", "SUPER": "Grocery", "SERVICENTRO": "Fuel"}
```

---

## 12. MISCELLANEOUS TIPS (Page 3)

### Truthy/Falsy for validations
```python
# ✅ GOOD: Leverage truthy/falsy
transaction_data = parse_email(html)

if transaction_data:  # Instead of: if transaction_data != {}
    process_transaction(transaction_data)
else:
    logger.warning("Could not parse email")

emails = check_gmail()

if not emails:  # Instead of: if len(emails) == 0
    logger.info("No new emails")
    return
```

### Swap variables
```python
# ✅ GOOD: Pythonic swap
x, y = y, x

# ❌ BAD: Traditional swap
temp = x
x = y
y = temp
```

### Remove duplicates preserving order
```python
# List of previously categorized merchants
merchants = ["MXM", "SUPER", "MXM", "UBER", "SUPER"]

# ✅ GOOD: Preserves order
unique_merchants = list(dict.fromkeys(merchants))
# ["MXM", "SUPER", "UBER"]
```

---

## 📋 CLEAN CODE CHECKLIST

Before committing, verify:

- [ ] **Descriptive names**: Variables with descriptive snake_case
- [ ] **Docstrings**: All functions have docstrings
- [ ] **Type hints**: Functions have types in parameters and return
- [ ] **Error handling**: Try-except on critical operations
- [ ] **Logging**: Info/Warning/Error appropriately
- [ ] **No dead code**: No unnecessary comments or old code
- [ ] **Imports ordered**: Standard → Third-party → Local
- [ ] **Constants in UPPERCASE**: `SPREADSHEET_ID`, `API_KEY`
- [ ] **F-strings**: Use f-strings instead of concatenation
- [ ] **Comprehensions**: Use when they improve readability

---

## 🚫 ANTI-PATTERNS TO AVOID

```python
# ❌ BAD: Non-descriptive variable names
d = get_data()
x = d['c']

# ✅ GOOD
transaction_data = get_transaction_data()
merchant = transaction_data['merchant']

# ---

# ❌ BAD: No error handling
response = requests.get(api_url)
data = response.json()

# ✅ GOOD
try:
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.Timeout:
    logger.error("API request timeout")
    raise
except requests.RequestException as e:
    logger.error(f"API error: {e}")
    raise

# ---

# ❌ BAD: String concatenation
message = "Error in email ID: " + str(email_id) + " with merchant: " + merchant

# ✅ GOOD: F-string
message = f"Error in email ID: {email_id} with merchant: {merchant}"

# ---

# ❌ BAD: Redundant comparison
if is_valid == True:
    process()

# ✅ GOOD
if is_valid:
    process()
```

---

## 🎓 EXECUTIVE SUMMARY

### For Antigravity:

1. **Always use f-strings** for string formatting
2. **Docstrings on all functions** with Args/Returns/Raises
3. **Try-except-finally** for I/O and API operations
4. **Appropriate logging**: info/warning/error by context
5. **Type hints** on function parameters and returns
6. **Comprehensions** when they improve readability
7. **Pathlib** for file path handling
8. **with statements** for files and resources
9. **Descriptive names** in snake_case
10. **Organized imports** in 3 blocks

**Priority**: Readable code > Short code

---

## 📚 SPECIFIC PATTERNS FOR THIS PROJECT

### Environment Variable Loading
```python
import os
import json

# ✅ GOOD: Load JSON from environment
def load_google_credentials() -> dict:
    """Load Google credentials from environment variable."""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS not found in environment")
    
    return json.loads(creds_json)
```

### Gmail API Pattern
```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# ✅ GOOD: Build service with error handling
def get_gmail_service() -> Any:
    """Create Gmail API service."""
    try:
        creds_dict = load_google_credentials()
        token_dict = load_google_token()
        
        creds = Credentials.from_authorized_user_info(token_dict)
        service = build('gmail', 'v1', credentials=creds)
        
        return service
    except Exception as e:
        logger.error(f"Failed to create Gmail service: {e}")
        raise
```

### Sheets API Pattern
```python
# ✅ GOOD: Append row with validation
def append_row_to_sheet(data: List[str], sheet_id: str) -> bool:
    """Append row to Google Sheet."""
    try:
        service = get_sheets_service()
        
        body = {'values': [data]}
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range='A:Z',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        rows_updated = result.get('updates', {}).get('updatedRows', 0)
        logger.info(f"Added {rows_updated} row(s) to sheet")
        
        return rows_updated > 0
    
    except Exception as e:
        logger.error(f"Failed to append row: {e}")
        return False
```

### Gemini API Pattern
```python
import google.generativeai as genai

# ✅ GOOD: Configure once, use many times
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('models/gemini-2.5-flash-lite')

def categorize_with_ai(merchant: str) -> str:
    """Categorize merchant using Gemini."""
    try:
        prompt = build_categorization_prompt(merchant)
        response = model.generate_content(prompt)
        category = response.text.strip()
        
        if validate_category(category):
            return category
        else:
            logger.warning(f"Invalid category: {category}")
            return "Uncategorized"
    
    except Exception as e:
        logger.error(f"AI categorization failed: {e}")
        return "Uncategorized"
```

---

✅ **Complete Reference**: See `python-cheatsheet.pdf` attached
