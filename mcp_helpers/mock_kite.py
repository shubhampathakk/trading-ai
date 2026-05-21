import json
import time
import random
import urllib.request
import logging
import ssl
from datetime import datetime, timedelta

# Bypass SSL verification globally for local mock environment fetches
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# Mock exceptions to mimic kiteconnect exceptions
class mock_exceptions:
    class KiteException(Exception): pass
    class TokenException(KiteException): pass
    class InputException(KiteException): pass
    class OrderException(KiteException): pass
    class NetworkException(KiteException): pass

class MockKiteConnect:
    """
    A high-fidelity mock of Zerodha's KiteConnect SDK.
    Fetches live, real-time Nifty 50 index data from public Yahoo Finance APIs,
    simulates margins, profiles, and executes paper-trading orders in-memory
    without requiring paid Zerodha Developer API credentials.
    """
    def __init__(self, api_key, access_token=None, *args, **kwargs):
        self.api_key = api_key
        self.access_token = access_token
        self.session_expiry = datetime.now() + timedelta(days=1)
        print("[MockKite] Initialized Mock Kite Connect Client (MOCK MODE ACTIVE)", flush=True)

    def login_url(self):
        return "https://kite.zerodha.com/connect/login?api_key=mock_key"

    def generate_session(self, request_token, api_secret):
        print(f"[MockKite] Generating mock session for request token: {request_token}", flush=True)
        return {
            "access_token": "mock_access_token_xyz123",
            "user_id": "MOCK_USER"
        }

    def set_access_token(self, access_token):
        self.access_token = access_token

    def profile(self):
        return {
            "user_id": "CZ3218",
            "user_name": "Shubham Pathak (Mock Agent)",
            "user_shortname": "Shubham",
            "email": "shubhampathak24@yahoo.com",
            "broker": "ZERODHA",
            "user_type": "individual",
            "exchanges": ["NSE", "BSE", "NFO", "BFO", "MF"],
            "products": ["CNC", "NRML", "MIS", "BO", "CO"],
            "order_types": ["MARKET", "LIMIT", "SL", "SL-M"]
        }

    def margins(self):
        return {
            "equity": {
                "enabled": True,
                "net": 100000.00,
                "available": {
                    "adhoc_margin": 0,
                    "cash": 100000.00,
                    "collateral": 0,
                    "intraday_payin": 0,
                    "live_balance": 100000.00,
                    "opening_balance": 100000.00
                },
                "utilised": {
                    "debits": 0,
                    "exposure": 0,
                    "m2m_realised": 0,
                    "m2m_unrealised": 0,
                    "option_premium": 0,
                    "payout": 0,
                    "span": 0,
                    "holding_sales": 0,
                    "turnover": 0,
                    "liquid_collateral": 0,
                    "stock_collateral": 0,
                    "delivery": 0
                }
            }
        }

    def _fetch_nifty_spot_yfinance(self) -> float:
        """Fetches real-time Nifty 50 Spot price from Yahoo Finance."""
        url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=^NSEI"
        try:
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                result = data.get("quoteResponse", {}).get("result", [])
                if result:
                    price = float(result[0].get("regularMarketPrice", 0))
                    if price > 0:
                        return price
        except Exception as e:
            logging.debug(f"[MockKite] Failed to fetch live Nifty spot: {e}")
        # Fallback to a realistic Nifty spot baseline
        return 22450.00 + random.uniform(-20, 20)

    def ltp(self, keys):
        """
        Simulates Last Traded Price for index or dynamic weekly options.
        Takes either a single key string or list of keys.
        """
        if isinstance(keys, str):
            keys = [keys]
            
        spot = self._fetch_nifty_spot_yfinance()
        res = {}
        
        for key in keys:
            if "NIFTY 50" in key or "NSE:NIFTY 50" in key or "^NSEI" in key or "NSE:NIFTY_50" in key:
                res[key] = {"instrument_token": 256265, "last_price": spot}
            elif "INDIAVIX" in key or "NSE:INDIAVIX" in key or "INDIA VIX" in key or "NSE:INDIA VIX" in key:
                res[key] = {"instrument_token": 264969, "last_price": 14.2 + random.uniform(-0.5, 0.5)}
            elif "CE" in key or "PE" in key:
                # Option pricing simulation based on strike and spot
                try:
                    # Extract strike price from option symbol e.g., NIFTY25MAY22400CE
                    strike_match = re.search(r'(\d{5})(CE|PE)', key)
                    if strike_match:
                        strike = float(strike_match.group(1))
                        is_call = strike_match.group(2) == "CE"
                        diff = spot - strike if is_call else strike - spot
                        
                        # Intrinsic value + simulated time value
                        intrinsic = max(0.0, diff)
                        time_val = 45.0 + random.uniform(-5, 5)
                        res[key] = {"instrument_token": 100000 + random.randint(0, 99999), "last_price": round(intrinsic + time_val, 2)}
                        continue
                except Exception:
                    pass
                # Generic option fallback
                res[key] = {"instrument_token": 55555, "last_price": 85.50 + random.uniform(-2, 2)}
            else:
                res[key] = {"instrument_token": 99999, "last_price": 100.0 + random.uniform(-1, 1)}
                
        return res

    def instruments(self, exchange=None):
        """Generates a realistic instruments lookup dataframe list."""
        spot = self._fetch_nifty_spot_yfinance()
        atm_strike = round(spot / 50) * 50
        
        instruments_list = [
            # Index Spot
            {
                "instrument_token": 256265,
                "exchange_token": "256265",
                "tradingsymbol": "NIFTY 50",
                "name": "NIFTY 50",
                "last_price": spot,
                "expiry": "",
                "strike": 0.0,
                "tick_size": 0.05,
                "lot_size": 50,
                "instrument_type": "EQ",
                "segment": "NSE",
                "exchange": "NSE"
            },
            # India VIX
            {
                "instrument_token": 264969,
                "exchange_token": "264969",
                "tradingsymbol": "INDIA VIX",
                "name": "INDIA VIX",
                "last_price": 14.2,
                "expiry": "",
                "strike": 0.0,
                "tick_size": 0.01,
                "lot_size": 1,
                "instrument_type": "EQ",
                "segment": "NSE",
                "exchange": "NSE"
            }
        ]
        
        # Generate option strikes dynamically around ATM
        for i in range(-10, 11):
            strike = atm_strike + (i * 50)
            # Weekly Expiry
            expiry_date = (datetime.now() + timedelta(days=(3 - datetime.now().weekday()) % 7)).strftime("%Y-%m-%d")
            expiry_sym = (datetime.now() + timedelta(days=(3 - datetime.now().weekday()) % 7)).strftime("%y%b").upper()
            
            for opt_type in ["CE", "PE"]:
                symbol = f"NIFTY{expiry_sym}{strike}{opt_type}"
                instruments_list.append({
                    "instrument_token": 100000 + random.randint(0, 99999),
                    "exchange_token": str(100000 + random.randint(0, 99999)),
                    "tradingsymbol": symbol,
                    "name": "NIFTY",
                    "last_price": 50.0,
                    "expiry": expiry_date,
                    "strike": float(strike),
                    "tick_size": 0.05,
                    "lot_size": 50,
                    "instrument_type": opt_type,
                    "segment": "NFO-OPT",
                    "exchange": "NFO"
                })
                
        return instruments_list

    def historical_data(self, instrument_token, from_date, to_date, interval, continuous=False, oi=False):
        """
        Fetches true historical 5m NIFTY 50 candles from Yahoo Finance,
        and formats them precisely into the pandas dataframe dictionary expected by the bot.
        """
        print(f"[MockKite] Fetching live historical data for token {instrument_token} from {from_date} to {to_date}", flush=True)
        
        # Build Yahoo Finance chart API request for Nifty index
        # Interval mapping: 5minute -> 5m, 15minute -> 15m, day -> 1d
        yf_interval = "5m"
        if "15" in str(interval):
            yf_interval = "15m"
        elif "day" in str(interval):
            yf_interval = "1d"
            
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/^NSEI?interval={yf_interval}&range=5d"
        
        try:
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req) as response:
                raw_data = json.loads(response.read().decode('utf-8'))
                chart = raw_data.get("chart", {}).get("result", [])[0]
                timestamps = chart.get("timestamp", [])
                indicators = chart.get("indicators", {}).get("quote", [])[0]
                
                candles = []
                for idx, ts in enumerate(timestamps):
                    dt = datetime.fromtimestamp(ts)
                    
                    # Filter date range
                    dt_str = dt.strftime("%Y-%m-%d")
                    if str(from_date) <= dt_str <= str(to_date):
                        c_open = indicators.get("open", [])[idx]
                        c_high = indicators.get("high", [])[idx]
                        c_low = indicators.get("low", [])[idx]
                        c_close = indicators.get("close", [])[idx]
                        c_volume = indicators.get("volume", [])[idx] or 0
                        
                        # Remove incomplete candles
                        if c_open and c_high and c_low and c_close:
                            candles.append({
                                "date": dt,
                                "open": float(c_open),
                                "high": float(c_high),
                                "low": float(c_low),
                                "close": float(c_close),
                                "volume": int(c_volume),
                                "oi": 0
                            })
                            
                if candles:
                    print(f"[MockKite] Retrieved {len(candles)} live historical candles from Yahoo Finance.", flush=True)
                    return candles
        except Exception as e:
            print(f"[MockKite] YFinance fetch failed: {e}. Generating simulated candles...", flush=True)
            
        # Fallback simulated candles in case Yahoo API fails
        candles = []
        current_price = 22450.00
        dt = datetime.now() - timedelta(days=5)
        
        for i in range(500):
            dt += timedelta(minutes=5)
            if dt.hour < 9 or (dt.hour == 9 and dt.minute < 15) or dt.hour > 15 or (dt.hour == 15 and dt.minute > 30) or dt.weekday() >= 5:
                continue
            o = current_price + random.uniform(-5, 5)
            h = o + random.uniform(0, 10)
            l = o - random.uniform(0, 10)
            c = random.uniform(l, h)
            candles.append({
                "date": dt,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": random.randint(1000, 50000),
                "oi": 0
            })
            current_price = c
            
        return candles

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type, price=None, trigger_price=None, **kwargs):
        order_id = str(random.randint(240000000, 250000000))
        print(f"[MockKite] ORDER PLACED: {transaction_type} {quantity} lots of {tradingsymbol} ({product}). ID: {order_id}", flush=True)
        return {"order_id": order_id}

    def modify_order(self, variety, order_id, parent_order_id=None, quantity=None, price=None, order_type=None, trigger_price=None, **kwargs):
        print(f"[MockKite] ORDER MODIFIED: ID: {order_id}, Price: {price}", flush=True)
        return {"order_id": order_id}

    def cancel_order(self, variety, order_id, parent_order_id=None):
        print(f"[MockKite] ORDER CANCELLED: ID: {order_id}", flush=True)
        return {"order_id": order_id}
