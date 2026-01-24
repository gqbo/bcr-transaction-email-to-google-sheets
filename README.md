# BCR Email to Google Sheets

Automatically sync BCR bank transaction emails to Google Sheets using GitHub Actions.

## Supported Transaction Types

- **Card Transactions** - Purchases and payments with BCR cards
- **SINPE Debit** - Money sent via SINPE mobile
- **SINPE Credit** - Money received via SINPE mobile

## Features

- Automated hourly sync via GitHub Actions
- AI-powered merchant categorization (Google Gemini)
- Direct Google Sheets integration
- Stateless architecture (no database needed)

## Setup

### 1. Google Cloud Configuration

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Gmail API** and **Google Sheets API**
3. Configure OAuth consent screen (External, add your email as test user)
4. Create OAuth credentials (Desktop app) and download `credentials.json`
5. Get a [Gemini API Key](https://aistudio.google.com/)

### 2. Generate Token Locally

```bash
pip install -r requirements.txt
python generate_token.py
```

This opens your browser for Google authentication and creates `token.json`.

### 3. GitHub Secrets

Add these secrets in your repository settings (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `GOOGLE_CREDENTIALS` | Contents of `credentials.json` |
| `GOOGLE_TOKEN` | Contents of `token.json` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SPREADSHEET_ID` | Google Sheet ID from URL |

### 4. Run

The workflow runs automatically every hour. To trigger manually:
1. Go to Actions tab
2. Select "BCR Bank Email Sync"
3. Click "Run workflow"

## Configuration

Adjust schedule in `.github/workflows/sync.yml`:

```yaml
schedule:
  - cron: '0 * * * *'  # Every hour
```

## Local Testing

```bash
export GOOGLE_CREDENTIALS=$(cat credentials.json)
export GOOGLE_TOKEN=$(cat token.json)
export GEMINI_API_KEY="your-api-key"
export SPREADSHEET_ID="your-sheet-id"

python main.py
```
