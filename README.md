# BCR Email to Google Sheets

Automatically sync BCR bank transaction emails to Google Sheets with AI-powered categorization.

## Supported Emails

- BCR Card Transactions
- SINPEMOVIL (sent/received)

## Quick Start

1. **Fork** this repository
2. **Copy config:**
   ```bash
   cp config/categories.yaml.example config/categories.yaml
   ```
3. **Customize** categories in `config/categories.yaml`
4. **Get credentials** (see setup below)
5. **Add GitHub secrets**
6. **Set up cron-job.org**

---

## Setup

### 1. Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Gmail API** and **Google Sheets API**
4. Go to **OAuth consent screen** → External → Add your email as Test User
5. Go to **Credentials** → Create OAuth client ID → Desktop app → Download JSON as `credentials.json`

### 2. Generate Token

```bash
pip install -r requirements.txt
python generate_token.py
```

This creates `token.json`.

### 3. Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create API Key

### 4. Google Sheet

1. Create a new spreadsheet in [Google Sheets](https://sheets.google.com/)
2. Copy the ID from the URL: `docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`

### 5. GitHub Secrets

Go to your fork → **Settings** → **Secrets and variables** → **Actions**

| Secret | Value |
|--------|-------|
| `GOOGLE_CREDENTIALS` | Contents of `credentials.json` |
| `GOOGLE_TOKEN` | Contents of `token.json` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SPREADSHEET_ID` | Your Sheet ID |

### 6. cron-job.org

GitHub Actions scheduled workflows are unreliable. Use [cron-job.org](https://cron-job.org/) instead.

**Create a GitHub Personal Access Token:**
1. Go to [GitHub Tokens](https://github.com/settings/tokens)
2. Generate new token (classic) with `repo` scope
3. Copy the token

**Create cron job:**

| Setting | Value |
|---------|-------|
| URL | `https://api.github.com/repos/YOUR_USERNAME/bcr-transaction-email-to-google-sheets/actions/workflows/sync.yml/dispatches` |
| Method | POST |
| Schedule | Every 8 hours |

**Headers:**

| Key | Value |
|-----|-------|
| Accept | `application/vnd.github+json` |
| Authorization | `Bearer YOUR_GITHUB_TOKEN` |
| Content-Type | `application/json` |
| X-GitHub-Api-Version | `2022-11-28` |

**Body:**
```json
{"ref":"main"}
```

---

## Syncing Updates

When the main repo updates:
1. Click "Sync fork" on GitHub
2. Your `categories.yaml` won't be affected (it's gitignored)

---

## Troubleshooting

**No emails found:** Check for unread BCR/SINPEMOVIL emails in Gmail

**Token expired:** Re-run `python generate_token.py` and update `GOOGLE_TOKEN` secret

**Permission denied:** Ensure APIs are enabled and your email is a Test User
