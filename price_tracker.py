"""
Price Tracker -- Monitors product pages daily and emails you when a price drops.

Runs as a GitHub Actions workflow (secrets stored in GitHub).
Also works locally using config.local.json.

Dependencies: pip install requests beautifulsoup4
"""

import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# --- Config loader (mirrors voip_report.py pattern) --------------------------

def load_config() -> dict:
    path = os.environ.get("PRICE_TRACKER_CONFIG", "config.local.json")
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return config


def required(name: str, cfg: dict) -> str:
    value = os.environ.get(name) or cfg.get(name)
    if not value:
        raise SystemExit(
            f"Missing required setting: {name}. "
            "Add it to config.local.json or set the environment variable."
        )
    return value


CONFIG = load_config()

SMTP_HOST   = "smtp.gmail.com"
SMTP_PORT   = 587
EMAIL_USER  = required("EMAIL_USER", CONFIG)
EMAIL_PASS  = required("EMAIL_PASS", CONFIG)
RECIPIENT   = required("EMAIL_RECIPIENT", CONFIG)

# --- Products to track -------------------------------------------------------
# Add more dicts here to track additional URLs.
PRODUCTS = [
    {
        "name": "Bear YSH-C18R1",
        "url":  "https://huarenstore.ca/bear-ysh-c18r1.html",
        # Only alert when price drops below this amount (CAD).
        # Set to None to alert on any price drop vs. yesterday.
        "alert_below": None,
    },
]

# File that stores last-known prices (committed back to repo by the workflow)
HISTORY_FILE = Path(__file__).parent / "price_history.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}


# --- Price history (JSON file, committed to repo) ----------------------------

def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_history(history: dict) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# --- Scraping ----------------------------------------------------------------

def fetch_price(url: str) -> tuple:
    """
    Returns (price_float, currency_str).  Strategy:
      1. <meta property="product:price:amount">  <- works on huarenstore.ca
      2. JSON-LD schema.org Product
      3. <meta itemprop="price">
      4. Common CSS selectors fallback
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. OpenGraph meta tag (confirmed working on huarenstore.ca)
    og = soup.find("meta", property="product:price:amount")
    if og and og.get("content"):
        cur_tag  = soup.find("meta", property="product:price:currency")
        currency = cur_tag["content"] if cur_tag else "CAD"
        try:
            return float(og["content"]), currency
        except ValueError:
            pass

    # 2. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") == "Product":
                offers   = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                price    = offers.get("price") or offers.get("lowPrice")
                currency = offers.get("priceCurrency", "CAD")
                if price is not None:
                    return float(price), currency
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    # 3. itemprop meta
    itemprop = soup.find("meta", itemprop="price")
    if itemprop and itemprop.get("content"):
        try:
            return float(itemprop["content"]), "CAD"
        except ValueError:
            pass

    # 4. CSS selectors fallback
    for sel in [
        ".price-new", ".price-tax", ".product-price",
        "[itemprop='price']", "span.price",
        ".woocommerce-Price-amount", "[class*='sale-price']",
    ]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"\d[\d,]*\.?\d*", el.get_text().replace(",", ""))
            if m:
                try:
                    return float(m.group().replace(",", "")), "CAD"
                except ValueError:
                    pass

    return None, "CAD"


# --- Email -------------------------------------------------------------------

def send_drop_alert(product: dict, old_price: float, new_price: float, currency: str) -> None:
    drop = old_price - new_price
    pct  = drop / old_price * 100
    sym  = currency

    subject = f"Price Drop Alert: {product['name']} is now {sym}${new_price:.2f}!"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body_html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#333">
<h2 style="color:#2ecc71">Price Drop Alert!</h2>
<table style="border-collapse:collapse;width:100%">
  <tr style="background:#f8f9fa">
    <td style="padding:8px;font-weight:bold">Product</td>
    <td style="padding:8px">{product['name']}</td>
  </tr>
  <tr>
    <td style="padding:8px;font-weight:bold">Old Price</td>
    <td style="padding:8px;text-decoration:line-through;color:#999">{sym}${old_price:.2f}</td>
  </tr>
  <tr style="background:#f8f9fa">
    <td style="padding:8px;font-weight:bold">New Price</td>
    <td style="padding:8px;color:#2ecc71;font-size:1.3em;font-weight:bold">{sym}${new_price:.2f}</td>
  </tr>
  <tr>
    <td style="padding:8px;font-weight:bold">You Save</td>
    <td style="padding:8px;color:#2ecc71">{sym}${drop:.2f} ({pct:.1f}% off)</td>
  </tr>
  <tr style="background:#f8f9fa">
    <td style="padding:8px;font-weight:bold">Checked At</td>
    <td style="padding:8px">{now_str}</td>
  </tr>
</table>
<br>
<a href="{product['url']}"
   style="background:#2ecc71;color:white;padding:12px 24px;
          text-decoration:none;border-radius:4px;display:inline-block">
  Buy Now
</a>
<p style="font-size:12px;color:#999;margin-top:24px">
  Price Tracker -- {product['url']}
</p>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_USER
    msg["To"]      = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print(f"  [email] Alert sent to {RECIPIENT}")


# --- Main --------------------------------------------------------------------

def run() -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"Price Tracker  --  {now_str}")
    print(f"{'='*60}")

    history = load_history()
    changed = False
    errors  = []

    for product in PRODUCTS:
        print(f"\n[product] {product['name']}")
        print(f"   {product['url']}")

        try:
            current_price, currency = fetch_price(product["url"])
        except requests.RequestException as exc:
            msg = f"Network error: {exc}"
            print(f"  [error] {msg}")
            errors.append(f"{product['name']}: {msg}")
            continue

        if current_price is None:
            msg = "Could not parse price from page"
            print(f"  [error] {msg}")
            errors.append(f"{product['name']}: {msg}")
            continue

        print(f"  [price] Current: {currency}${current_price:.2f}")

        entry      = history.get(product["url"], {})
        last_price = entry.get("price")

        # Always update history with today's price
        history[product["url"]] = {
            "name":       product["name"],
            "price":      current_price,
            "currency":   currency,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        changed = True

        alert_below = product.get("alert_below")

        if last_price is None:
            print(f"  [info] First run -- baseline {currency}${current_price:.2f} recorded.")
        elif current_price < last_price:
            drop_pct = (last_price - current_price) / last_price * 100
            print(
                f"  [drop] PRICE DROP: {currency}${last_price:.2f} -> "
                f"{currency}${current_price:.2f}  ({drop_pct:.1f}% off)"
            )
            if alert_below is None or current_price <= alert_below:
                try:
                    send_drop_alert(product, last_price, current_price, currency)
                except Exception as exc:
                    print(f"  [error] Email failed: {exc}")
                    errors.append(f"Email error: {exc}")
            else:
                print(f"  [info] Drop noted but above alert threshold {currency}${alert_below:.2f}")
        elif current_price > last_price:
            print(f"  [up]   Price INCREASED: {currency}${last_price:.2f} -> {currency}${current_price:.2f}")
        else:
            print(f"  [same] Price unchanged at {currency}${current_price:.2f}")

    if changed:
        save_history(history)
        print("\n[saved] price_history.json updated.")

    if errors:
        print("\n[warn] Errors encountered:")
        for e in errors:
            print(f"   * {e}")
        sys.exit(1)

    print(f"\n{'='*60}\nDone.\n")


if __name__ == "__main__":
    run()
