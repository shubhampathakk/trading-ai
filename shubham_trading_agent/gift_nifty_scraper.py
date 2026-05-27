import urllib.request
import json
import ssl
import logging
import datetime
from bs4 import BeautifulSoup

def fetch_gift_nifty_gap(prior_nifty_close: float) -> float:
    """
    Scrapes the live Gift Nifty price from public Moneycontrol feeds.
    Compares it to yesterday's Nifty 50 close to calculate the projected opening gap %.
    Returns a signed float (e.g., +0.45 for a gap up, -0.25 for a gap down).
    Falls back to 0.0 seamlessly if endpoints are rate-limiting or down.
    """
    if prior_nifty_close <= 0:
        return 0.0

    print("[Gift Nifty Scraper] Fetching live international footprints...", flush=True)
    
    url = "https://priceapi.moneycontrol.com/pricefeed/notapplicable/inidices/globalindices"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.moneycontrol.com/markets/global-indices/"
    }

    try:
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=7) as response:
            raw_data = json.loads(response.read().decode('utf-8'))
            
            # Find GIFT Nifty entry inside the global indices list
            gift_nifty_price = 0.0
            indices_list = raw_data.get("data", []) or []
            
            for item in indices_list:
                name = item.get("name", "").upper()
                if "GIFT NIFTY" in name or "SGX NIFTY" in name:
                    # Strip commas out of streaming string formats
                    price_str = str(item.get("lastPrice", "0")).replace(",", "").strip()
                    gift_nifty_price = float(price_str)
                    break
            
            if gift_nifty_price > 0:
                # Math: Calculate exact signed percentage difference
                signed_gap = ((gift_nifty_price - prior_nifty_close) / prior_nifty_close) * 100.0
                print(f"[Gift Nifty Scraper] Live Price: {gift_nifty_price:,.2f} | Prior Nifty Close: {prior_nifty_close:,.2f}")
                print(f"[Gift Nifty Scraper] Predicted Opening Gap: {signed_gap:+.2f}%", flush=True)
                return round(signed_gap, 3)
                
    except Exception as e:
        logging.warning(f"[Gift Nifty Scraper] Primary API handshake failed ({e}). Attempting HTML scraper fallback...")
        
    # --- Secondary HTML Scraping Fallback ---
    try:
        fallback_url = "https://www.moneycontrol.com/markets/global-indices/"
        req_fallback = urllib.request.Request(fallback_url, headers={"User-Agent": "Mozilla/5.0"})
        
        with urllib.request.urlopen(req_fallback, context=ssl_ctx, timeout=7) as response:
            soup = BeautifulSoup(response.read(), 'html.parser')
            # Look up moneycontrol's global indices table structures
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if cells and any("GIFT NIFTY" in c.text.upper() for c in cells):
                    price_text = cells[1].text.replace(",", "").strip()
                    gift_nifty_price = float(price_text)
                    signed_gap = ((gift_nifty_price - prior_nifty_close) / prior_nifty_close) * 100.0
                    print(f"[Gift Nifty Scraper] Fallback Success! Predicted Open: {signed_gap:+.2f}%")
                    return round(signed_gap, 3)
    except Exception as fallback_err:
        logging.error(f"[Gift Nifty Scraper] All pre-market routing options exhausted: {fallback_err}")

    print("[Gift Nifty Scraper] Fallback activated. Defaulting open gap to 0.00% (Flat Open).")
    return 0.0
