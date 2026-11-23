# Price Tracker

Monitors product pages daily and emails you when a price drops.
Runs free on **GitHub Actions** — no server or PC needed.

## How it works

```
GitHub Actions (cron 9 AM daily)
  → runs price_tracker.py
  → fetches price from product page (via meta tags — reliable, no JS needed)
  → compares to price_history.json (committed in the repo)
  → emails you if price dropped
  → commits updated price_history.json back to repo
```

---

## Setup: Push to GitHub and add secrets

### 1. Create a new GitHub repo and push

```powershell
cd "c:\github\price tracker"
git remote add origin https://github.com/YOUR_USERNAME/price-tracker.git
git push -u origin master
```

### 2. Add these GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `EMAIL_USER` | `mklucky01@gmail.com` |
| `EMAIL_PASS` | your Gmail App Password |
| `EMAIL_RECIPIENT` | `mklucky01@gmail.com` |

> Your App Password is in `config.local.json` (gitignored, never pushed).

### 3. Enable Actions

Go to your repo → **Actions** tab → click **"I understand my workflows, go ahead and enable them"**

That's it. The workflow runs daily at 9 AM Mountain Time automatically.

---

## Add more products to track

Edit `PRODUCTS` in `price_tracker.py`:

```python
PRODUCTS = [
    {
        "name": "Bear YSH-C18R1",
        "url":  "https://huarenstore.ca/bear-ysh-c18r1.html",
        "alert_below": None,   # None = alert on any drop
    },
    {
        "name": "Some Other Product",
        "url":  "https://example.com/product.html",
        "alert_below": 50.0,   # only alert if price drops below $50
    },
]
```

Then `git commit` and `git push` — the workflow picks up the change automatically.

---

## Run locally (for testing)

```powershell
cd "c:\github\price tracker"
python price_tracker.py
```

Credentials are read from `config.local.json` (gitignored).

---

## Files

| File | Purpose |
|---|---|
| `price_tracker.py` | Main script |
| `price_history.json` | Last-known prices (auto-updated by workflow) |
| `config.local.json` | Local credentials — **never committed** |
| `.github/workflows/daily-tracker.yml` | GitHub Actions schedule |
| `requirements.txt` | Python dependencies |
