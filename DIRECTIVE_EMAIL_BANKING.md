# DIRECTIVE: BCR Bank Email to Google Sheets Automation System

## 🎯 PRIMARY OBJECTIVE
Create a Python-based system that:
1. Monitors Gmail for BCR bank transaction emails
2. Extracts and parses transaction data
3. Uses AI (Gemini) to categorize merchants
4. Appends data to Google Sheets automatically
5. Runs hourly via GitHub Actions (stateless architecture)

## 📋 PROJECT CONTEXT

### Why This System?
- **Cost**: n8n charges per execution, Python + GitHub Actions is FREE
- **Determinism**: Controlled code vs visual nodes
- **Scalability**: Easy to maintain and version
- **Professionalism**: Production-ready deployment

### Core Philosophy
**Stateless Architecture**: Each execution is independent. GitHub Actions spins up a container, runs the script, and destroys it. No persistent state needed.

---

## 🏗️ ARCHITECTURE

### System Flow
```
GitHub Actions (Cron: Every Hour)
    ↓
Container starts (Ubuntu + Python 3.9)
    ↓
Load secrets from GitHub Repository Secrets
    ↓
main.py orchestrates:
    ├── gmail_checker.py → Check for unread emails
    ├── email_parser.py → Extract transaction data
    ├── ai_categorizer.py → Categorize merchant with Gemini
    └── sheets_writer.py → Append row to Google Sheets
    ↓
Container destroyed
```

### Key Principle: Stateless Operation
- ✅ No database needed
- ✅ No file storage needed
- ✅ Uses Gmail's "unread" status as state
- ✅ Each run is independent
- ✅ Free forever on GitHub Actions

---

## 📂 PROJECT STRUCTURE

```
bcr-gmail-sheets-sync/
├── .github/
│   └── workflows/
│       └── sync.yml                  # GitHub Actions workflow
│
├── src/
│   ├── __init__.py
│   ├── gmail_checker.py              # Gmail API connection
│   ├── email_parser.py               # HTML parsing logic
│   ├── ai_categorizer.py             # Gemini categorization
│   └── sheets_writer.py              # Google Sheets API
│
├── tests/
│   ├── test_email_parser.py          # Unit tests
│   └── fixtures/
│       └── sample_email.html         # Test data
│
├── config/
│   └── categories.py                 # Category definitions
│
├── main.py                           # Main orchestrator
├── requirements.txt                  # Python dependencies
├── .gitignore
└── README.md                         # Setup instructions
```

---

## 🔧 COMPONENTS TO IMPLEMENT

### 1. Gmail Checker (`src/gmail_checker.py`)

**Purpose**: Connect to Gmail API and retrieve unread BCR transaction emails

**Inputs**:
- Gmail credentials (from environment variables)
- Search query: `subject:"Notificación de Transacciones BCR" is:unread`

**Outputs**:
- List of email objects: `[{"id": "...", "html": "...", "subject": "..."}]`

**Logic**:
```python
1. Load credentials from environment (JSON string → dict)
2. Build Gmail API service
3. Search for emails matching query
4. For each email:
   a. Get full message content
   b. Extract HTML body
   c. Return structured data
5. Mark emails as read after successful processing
```

**Key Requirements**:
- Must handle OAuth tokens from environment variables
- Must not fail if no emails found (exit 0)
- Must extract HTML body correctly from MIME structure

**Dependencies**:
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`

**Python Cheatsheet References**:
- Functions (page 2)
- Exceptions with try-except (page 2)
- File I/O for logs (page 3)

---

### 2. Email Parser (`src/email_parser.py`)

**Purpose**: Extract structured transaction data from BCR email HTML

**Input**:
- HTML content (string)

**Output**:
- Dictionary:
  ```python
  {
      "date": "22/01/2024 14:30:45",
      "authorization": "123456",
      "reference": "789012",
      "amount": "15000.00",
      "currency": "CRC",
      "merchant": "MAS X MENOS DESAMPARADOS",
      "status": "Approved"
  }
  ```

**Logic** (based on current n8n JavaScript code):
```python
1. Parse HTML with BeautifulSoup
2. Find all <tbody> sections
3. For each tbody:
   a. Extract all <td> elements
   b. Clean text:
      - Remove HTML tags
      - Replace &nbsp; with space
      - Normalize whitespace (multiple spaces → single)
      - Strip leading/trailing spaces
   c. Filter empty values
4. Identify tbody with exactly 7 values (transaction data)
5. If found:
   - Map to structured dictionary
   - Validate required fields
6. If not found:
   - Fallback to plain text parsing
   - Use regex to find date pattern: \d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}
7. Raise exception if parsing fails completely
```

**Dependencies**:
- `beautifulsoup4`
- `lxml`
- Standard library `re` (regex)

**Python Cheatsheet References**:
- Strings & String Methods (page 1)
- Dictionaries (page 3)
- Functions with return (page 2)
- Exceptions (page 2)

**Improvements over n8n code**:
- Use BeautifulSoup instead of manual regex
- Add field validation
- Better error messages
- Type hints

---

### 3. AI Categorizer (`src/ai_categorizer.py`)

**Purpose**: Categorize merchant using Gemini AI

**Input**:
- Merchant name (string)

**Output**:
- Category name (string): "Mercado (alimentos, aseo hogar)", "Combustible", etc.

**Logic**:
```python
1. Load category configuration
2. Build prompt with:
   - Classification instructions
   - Keyword rules per category
   - Complete category list
   - Merchant to classify
3. Call Gemini 2.5 Flash
4. Parse response (extract category name)
5. Validate category exists in list
6. If validation fails:
   - Log warning
   - Return "Uncategorized"
7. Return category
```

**Complete Prompt** (to be used in code):

```
Classify this merchant into ONE category. Reply with ONLY the category name, nothing else.

Merchant: {merchant_name}

## CLASSIFICATION RULES (apply these first by searching keywords, case-insensitive):

🛒 Mercado (alimentos, aseo hogar)
Keywords: MXM, SUPER, MAS X MENOS, PRICE SMART, FRESK MARKET

⛽ Combustible
Keywords: SERVICENTRO, ESTACION

🍽️ Domicilios/restaurantes
Keywords: SODA, RESTAURANT, SUBWAY, CAFE, COFEE, PIZZA

💧 Agua
Keywords: AGUA

⚡ Electricidad
Keywords: ELECTRICIDAD, ICE

🌐 Internet
Keywords: INTERNET, CABLE

🚗 Transporte UBER
Keywords: UBER

📺 YouTube Premium
Keywords: YOUTUBE

🤖 Chat GPT
Keywords: GPT, CHATGPT

⚰️ Plan funerario
Keywords: FUNERARIO

🏠 Hipoteca Casa
Keywords: HIPOTECA, VIVIENDA

📱 Plan celular
Keywords: CELULAR, KOLBI, PLAN

## ALL VALID CATEGORIES (use if no keyword rule matches):
- Agua
- Agua Desamparados
- Chat GPT
- Combustible
- Consultas médicas
- Diversión
- Domicilios/restaurantes
- Educación
- Electricidad
- Fruta/Snacks/Café
- Hipoteca Casa
- Internet
- Mantenimiento vehículo
- Mantenimiento hogar
- Medicamentos
- Mercado (alimentos, aseo hogar)
- Mesada Gabriel
- Mesada Oscar
- Peluquería
- Plan celular
- Plan funerario
- Transporte UBER
- Vacaciones
- Vestuario (ropa/zapato/accesorios)
- YouTube Premium

Reply with ONLY the exact category name.
```

**Dependencies**:
- `google-generativeai`

**Model Configuration**:
```python
model_name = "models/gemini-2.5-flash-lite"
# Note: Use 2.5 flash lite for speed and cost efficiency
# Temperature: 0 (deterministic)
```

**Python Cheatsheet References**:
- Strings & f-strings (page 1)
- Functions (page 2)
- Conditionals (page 1)

**Optimizations**:
- Use temperature=0 for consistency
- Add retry logic with exponential backoff
- Log all categorizations for debugging

---

### 4. Sheets Writer (`src/sheets_writer.py`)

**Purpose**: Write transaction row to Google Sheets

**Input**:
- Transaction data (dict)
- Category (string)

**Output**:
- Success boolean
- Row number added

**Logic**:
```python
1. Load credentials from environment
2. Build Google Sheets API service
3. Prepare row:
   [Date, Reference, Amount, Merchant, Category, Status]
4. Determine spreadsheet ID (from env)
5. Append row to sheet using append() method
6. Log operation
7. Return success status
```

**Row Format** (matching current n8n setup):
```python
row = [
    transaction['date'],
    transaction['reference'],
    transaction['amount'],
    transaction['merchant'],
    category,
    transaction['status']
]
```

**Dependencies**:
- `google-api-python-client`
- `google-auth`

**Python Cheatsheet References**:
- Lists (page 3)
- Functions (page 2)
- Exceptions (page 2)

---

### 5. Main Orchestrator (`main.py`)

**Purpose**: Coordinate all components

**Logic**:
```python
1. Setup logging (console output for GitHub Actions)
2. Load configuration from environment
3. Validate all credentials present
4. Check Gmail for new emails
5. If no emails:
   - Log "No new emails"
   - Exit 0 (success)
6. For each email:
   a. Parse transaction data
   b. Categorize merchant
   c. Write to Sheets
   d. Mark email as read
   e. Handle errors gracefully
7. Print summary
8. Exit 0 (success)
```

**Error Handling Strategy**:
- Parse failure: Skip email, log error, continue
- Categorization failure: Use "Uncategorized"
- Sheets failure: Retry 3 times, then fail gracefully
- Never mark email as read if processing failed

**Python Cheatsheet References**:
- Loops with enumerate (page 2)
- Exceptions with try-except-finally (page 2)
- Functions (page 2)

---

## 🔐 CREDENTIALS & ENVIRONMENT SETUP

### Required Google Cloud Setup

**Step 1: Create Google Cloud Project**
1. Go to Google Cloud Console
2. Create new project
3. Enable APIs:
   - Gmail API
   - Google Sheets API

**Step 2: OAuth Consent Screen**
1. Configure as "External"
2. Add your email as "Test User"

**Step 3: Create OAuth Client ID**
1. Create "Desktop App" credentials
2. Download as `credentials.json`

**Step 4: Generate Token Locally**
```bash
# Run this ONCE on your local machine
python generate_token.py

# This will:
# 1. Open browser
# 2. Ask for Google login
# 3. Request permissions
# 4. Save token.json locally
```

**Step 5: Get Gemini API Key**
1. Go to Google AI Studio
2. Create API Key
3. Copy the key

### Environment Variables Strategy

**GitHub Secrets (never commit these)**:
- `GOOGLE_CREDENTIALS`: Full JSON content of credentials.json
- `GOOGLE_TOKEN`: Full JSON content of token.json
- `GEMINI_API_KEY`: Your Gemini API key
- `SPREADSHEET_ID`: Your Google Sheet ID

**Loading in Python**:
```python
import os
import json

# Load credentials from environment
credentials_json = os.environ['GOOGLE_CREDENTIALS']
credentials = json.loads(credentials_json)

token_json = os.environ['GOOGLE_TOKEN']
token = json.loads(token_json)

gemini_key = os.environ['GEMINI_API_KEY']
sheet_id = os.environ['SPREADSHEET_ID']
```

---

## 🔄 GITHUB ACTIONS WORKFLOW

### File: `.github/workflows/sync.yml`

```yaml
name: BCR Bank Email Sync

on:
  schedule:
    # Run every hour at minute 0
    - cron: '0 * * * *'
  
  # Allow manual trigger for testing
  workflow_dispatch:

jobs:
  sync-transactions:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up Python 3.9
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run sync script
        env:
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
          GOOGLE_TOKEN: ${{ secrets.GOOGLE_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          SPREADSHEET_ID: ${{ secrets.SPREADSHEET_ID }}
        run: python main.py
      
      - name: Upload logs (on failure)
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: error-logs
          path: logs/
```

---

## 📝 DEPENDENCIES (requirements.txt)

```txt
# Google APIs
google-api-python-client==2.108.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
google-auth==2.25.2

# Gemini AI
google-generativeai==0.3.2

# HTML Parsing
beautifulsoup4==4.12.2
lxml==4.9.3

# Utilities
python-dateutil==2.8.2

# Testing (optional)
pytest==7.4.3
```

---

## 🎨 CODE STANDARDS

### Follow Python Cheatsheet
- **Variable names**: snake_case
- **Functions**: Use docstrings with Args/Returns/Raises
- **Strings**: Use f-strings for formatting
- **Lists**: Use comprehensions when appropriate
- **Errors**: Try-except-finally for critical operations
- **Type hints**: Add to all function signatures

### Example of Well-Documented Function:
```python
def parse_bcr_email(html_content: str) -> dict:
    """
    Extract structured transaction data from BCR email HTML.
    
    Args:
        html_content: Complete HTML string from email
        
    Returns:
        Dictionary with fields: date, authorization, reference,
        amount, currency, merchant, status
        
    Raises:
        ValueError: If email cannot be parsed
    """
    # Implementation...
```

### Logging Standard:
```python
import logging

logger = logging.getLogger(__name__)

# In functions:
logger.info(f"Processing email ID: {email_id}")
logger.warning(f"No category found for: {merchant}")
logger.error(f"Error writing to Sheets: {e}")
```

---

## 🧪 TESTING STRATEGY

### Manual Test Script (`test_local.py`)
```python
# Run locally before deploying
from src.email_parser import parse_bcr_email

# Load sample email
with open('tests/fixtures/sample_email.html') as f:
    html = f.read()

# Test parser
result = parse_bcr_email(html)
print(result)

# Expected output:
# {
#   "date": "22/01/2024 14:30:45",
#   "merchant": "MAS X MENOS",
#   ...
# }
```

### Unit Tests (optional)
```python
# tests/test_email_parser.py
import pytest
from src.email_parser import parse_bcr_email

def test_parse_valid_email():
    html = load_fixture('valid_email.html')
    result = parse_bcr_email(html)
    assert result['merchant'] == 'MAS X MENOS'
    assert 'date' in result
```

---

## 🚀 DEPLOYMENT STEPS

### Phase 1: Local Development (1-2 days)
1. ✅ Implement `src/email_parser.py` (test with real emails)
2. ✅ Implement `src/ai_categorizer.py` (verify prompt works)
3. ✅ Implement `src/sheets_writer.py` (test write)
4. ✅ Implement `src/gmail_checker.py`
5. ✅ Integrate in `main.py`

### Phase 2: Local Testing (1 day)
1. Run `python main.py` locally
2. Verify it finds emails
3. Verify categorization matches expectations
4. Verify Sheet gets updated
5. Check logs are clear

### Phase 3: GitHub Setup (1 hour)
1. Create GitHub repository
2. Push code
3. Add GitHub Secrets:
   - Settings → Secrets → Actions → New repository secret
   - Add all 4 secrets
4. Enable Actions in repository settings

### Phase 4: First Run (testing)
1. Trigger workflow manually (Actions tab → Run workflow)
2. Watch logs in real-time
3. Verify email processed
4. Verify Sheet updated
5. Fix any issues

### Phase 5: Production (automated)
- Workflow runs automatically every hour
- Monitor GitHub Actions tab for failures
- Check emails are processed correctly

---

## 📊 SUCCESS METRICS

✅ **Completed when**:
1. Script processes BCR emails correctly
2. Parser extracts 100% of fields
3. Categorization has >95% accuracy
4. Data writes to Sheets without errors
5. Logs are clear and useful
6. Runs successfully on GitHub Actions
7. No failures for 1 week of hourly runs

---

## ⚠️ IMPORTANT CONSIDERATIONS

### Security
- ❌ NEVER commit credentials to Git
- ✅ Use .gitignore for credentials/ and .env
- ✅ Only store secrets in GitHub Secrets
- ✅ Rotate API keys periodically

### Rate Limits
- Gmail API: 250 queries/user/second (very generous)
- Sheets API: 100 requests/100 seconds/user
- Gemini: Depends on plan (free tier: 15 RPM)

### Costs
- Gmail API: Free
- Sheets API: Free
- Gemini 2.5 Flash: ~$0.0001 per categorization
- GitHub Actions: 2000 minutes/month free (this uses ~5 min/month)

**Total monthly cost: $0** (within free tiers)

---

## 🎯 INSTRUCTIONS FOR ANTIGRAVITY

### Step 1: Initial Setup
```
Create the project structure as specified in PROJECT STRUCTURE.
Generate requirements.txt with listed dependencies.
Create .gitignore excluding:
- credentials/
- token.json
- .env
- __pycache__/
- *.pyc
- logs/
```

### Step 2: Implement Components
```
Follow this order:
1. src/email_parser.py (easiest, no APIs)
2. src/ai_categorizer.py (requires Gemini API)
3. src/sheets_writer.py (requires Sheets API)
4. src/gmail_checker.py (requires Gmail API)
5. main.py (orchestrates everything)

For each component:
- Create in src/ directory
- Follow Input/Output/Logic specifications
- Use Python Cheatsheet references
- Add docstrings to all functions
- Handle errors with try-except
- Log important operations
```

### Step 3: Configuration
```
Generate config/categories.py with:
- Dictionary of keywords → category
- List of all valid categories
- Function to validate category
```

### Step 4: GitHub Actions
```
Create .github/workflows/sync.yml exactly as specified.
Ensure environment variables are loaded correctly.
Add error handling for missing secrets.
```

### Step 5: Documentation
```
Generate README.md with:
1. Project description
2. Prerequisites
3. Setup instructions (step-by-step)
4. How to obtain credentials
5. GitHub Secrets configuration
6. How to run locally
7. How to deploy to GitHub Actions
8. Troubleshooting section
```

### Step 6: Testing
```
Create test_local.py with:
- Function to test parser with real HTML
- Function to test categorization
- Function to test Sheets write

DO NOT implement automated tests yet.
```

---

## 🔄 SCALABILITY FOR OTHERS

If someone wants to use this system:

1. **Fork**: Fork the repository on GitHub
2. **Credentials**: Generate their own `credentials.json` and `token.json`
3. **Secrets**: Add their own values to GitHub Secrets
4. **Customize**: Adjust search query and categories if needed
5. **Done**: System runs independently and free

Each user has their own:
- Google Cloud project
- Gmail authentication
- Google Sheet
- GitHub Actions execution quota

**Result**: Infinite users, zero marginal cost, zero shared infrastructure.

---

## ✅ FINAL DELIVERABLES

When Antigravity completes this directive, you will have:

```
✅ Complete Python project structure
✅ All components implemented
✅ GitHub Actions workflow configured
✅ README with setup instructions
✅ Requirements.txt
✅ .gitignore
✅ Test script for local validation
✅ Clean, documented, professional code
✅ Ready to deploy and run hourly
```

---

## 💡 KEY ADVANTAGES OVER N8N

1. **Free Forever**: $0/month vs $20/month
2. **Version Control**: Full Git history
3. **Code Review**: Can review every change
4. **Testing**: Can write unit tests
5. **Debugging**: Full control over logs
6. **Scalability**: Anyone can fork and use
7. **Portability**: Can run anywhere (local, cloud, etc)
8. **Professional**: Real software engineering practices

---

**Success! 🚀**

Follow this directive to create a production-ready, maintainable, cost-free email automation system using Python and GitHub Actions.
