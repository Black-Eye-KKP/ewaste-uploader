# EVS E-Waste Analyser — Full Project

## Architecture

```
[GitHub Pages]          [Flask Server]         [Docker n8n]
 upload/index.html  →   POST /upload       →   Webhook node
  (secure upload)        validates image        AI Agent (Grok)
                         forwards to n8n        Build HTML report
                         saves report ←─────────POST /save-report
                        /metal-prices ←─────────market data node
```

---

## 1 — GitHub Pages Upload Page

**File:** `upload-page/index.html`

### Deploy to GitHub Pages
1. Push this repo to GitHub
2. Go to **Settings → Pages → Source → GitHub Actions**
3. The workflow (`.github/workflows/deploy.yml`) auto-deploys on push
4. Your upload page will be at: `https://<username>.github.io/<repo>/`

### Security features
- Extension whitelist (jpg, png, webp, gif, bmp)
- **Client-side magic-byte verification** (reads first 16 bytes)
- File size limit (20 MB)
- Duplicate file detection

---

## 2 — Flask Server

**File:** `flask-server/app.py`

### Install & run (Windows)
```bat
cd flask-server
pip install -r requirements.txt

:: Optional: set your own n8n webhook URL
set N8N_WEBHOOK_URL=http://localhost:5678/webhook/ewaste

:: Optional: change reports folder
set REPORTS_FOLDER=D:\EVS\EVs\Reports

python app.py
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Receive image from browser, validate, forward to n8n |
| POST | `/save-report` | Called by n8n to save the HTML report |
| POST | `/metal-prices` | Returns 12-month price data for given metals |
| GET | `/health` | Health check |

---

## 3 — n8n Workflow

**File:** `n8n_workflow.json`

### Import
1. Open n8n at `http://localhost:5678`
2. Click **+** → **Import from file** → select `n8n_workflow.json`
3. Add your **Grok API key**:
   - Open the **AI Agent — Grok Vision** node
   - Add a new credential: `xAI / Grok` → paste your free API key from [console.x.ai](https://console.x.ai)
4. Set the webhook to **Active** (toggle top-right)

### Workflow nodes
```
Webhook (POST /webhook/ewaste)
  → Read Binary File
  → AI Agent (Grok Vision) — analyses image, returns JSON
  → Parse AI Response (Code node)
  → GET /metal-prices from Flask
  → Build Report HTML (Code node — Plotly charts)
  → POST /save-report to Flask (saves to D:\EVS\EVs\Reports)
  → Respond with HTML
```

### Getting a free Grok API key
1. Go to [console.x.ai](https://console.x.ai)
2. Sign in with your X (Twitter) account
3. Create an API key
4. Free tier includes vision capability

---

## 4 — Report Aggregator Dashboard

**File:** `aggregator/aggregator.py`

Scans `D:\EVS\EVs\Reports` for all `.html` reports and builds a single
`dashboard.html` with a 3-icon sidebar, thumbnail list, and iframe viewer.

### Run
```bat
cd aggregator
python aggregator.py
```

The dashboard opens automatically in your browser.

### Change reports folder
```bat
set REPORTS_FOLDER=D:\EVS\EVs\Reports
python aggregator.py
```

---

## Quick Start (all together)

```bat
:: Terminal 1 — Flask server
cd flask-server
pip install -r requirements.txt
python app.py

:: Terminal 2 — open upload page (after GitHub Pages deploy, or just open locally)
start upload-page\index.html

:: After workflow runs and reports are saved:
:: Terminal 3 — build dashboard
cd aggregator
python aggregator.py
```
