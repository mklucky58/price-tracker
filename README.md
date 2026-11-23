# Price Tracker — Setup Guide

## What it does
- Visits the product page every day
- Records the price in a local SQLite database (`price_history.db`)
- Sends you an email if the price **drops**

---

## 1. Configure your email

Open `price_tracker.py` and fill in the `CONFIG` section:

```python
"email": {
    "sender":    "your_gmail@gmail.com",
    "password":  "xxxx xxxx xxxx xxxx",   # Gmail App Password (see below)
    "recipient": "your_gmail@gmail.com",
},
```

### Getting a Gmail App Password
1. Go to <https://myaccount.google.com/apppasswords>
2. Create a new app password (name it "Price Tracker")
3. Copy the 16-character code and paste it as `password`

> **Note:** 2-Step Verification must be enabled on your Google account first.

---

## 2. Add more products

Each product is a dict in `CONFIG["products"]`:

```python
{
    "name": "Some Product",
    "url":  "https://example.com/product-page",
    "price_selector": None,   # auto-detected, or paste a CSS selector
    "alert_below": 100.0,     # only alert if price drops below $100 (or None for any drop)
},
```

---

## 3. Test manually

```powershell
cd "c:\github\price tracker"
python price_tracker.py
```

---

## 4. Schedule daily with Windows Task Scheduler

Run once to create the task (run PowerShell as Administrator):

```powershell
$action  = New-ScheduledTaskAction -Execute "python" `
           -Argument '"c:\github\price tracker\price_tracker.py"'
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"
Register-ScheduledTask -TaskName "PriceTracker" `
    -Action $action -Trigger $trigger -RunLevel Highest
```

The script will run every day at 9 AM and email you if any price drops.

---

## Files
| File | Purpose |
|------|---------|
| `price_tracker.py` | Main script |
| `price_history.db` | SQLite database (auto-created on first run) |
| `README.md` | This file |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Could not parse a price" | Open the page, right-click the price → Inspect → copy the CSS selector into `price_selector` |
| Email not sent | Check App Password; make sure 2FA is on |
| Price always shows wrong value | The site may require JavaScript — open an issue or use Playwright instead of requests |
