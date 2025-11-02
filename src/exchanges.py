import os
import time
import math
import requests
from typing import Any, Dict, List, Optional, Tuple

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
BINANCE_FAPI = "https://fapi.binance.com"
BYBIT_PERP = "https://api.bybit.com"
OKX_BASE = "https://www.okx.com"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "spot-futures-recommender/1.0"})

def _get(url: str, params: Optional[Dict[str, Any]] = None, retries: int = 3, timeout: int = 15) -> Any:
    last_exc = None
    for _ in range(retries):
        try:
            resp = SESSION.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.0)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_exc = e
            time.sleep(0.7)
    if last_exc:
        raise last_exc

# ---------- CoinGecko ----------

def cg_top_coins(n: int = 50) -> List[Dict[str, Any]]:
    """Top n coins by market cap with spot prices."""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": n,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h,7d"
    }
    return _get(url, params=params)

# ---------- Binance Futures (USDT-margined) ----------

def binance_perp_exchange_info() -> Dict[str, Any]:
    return _get(f"{BINANCE_FAPI}/fapi/v1/exchangeInfo")

def binance_perp_premium_index(symbol: str) -> Optional[Dict[str, Any]]:
    """Mark price + funding rate next for symbol (e.g., BTCUSDT)."""
    try:
        data = _get(f"{BINANCE_FAPI}/fapi/v1/premiumIndex", params={"symbol": symbol})
        return data
    except:
        return None

def binance_open_interest(symbol: str) -> Optional[float]:
    try:
        data = _get(f"{BINANCE_FAPI}/futures/data/openInterestHist", params={"symbol": symbol, "period": "5m", "limit": 1})
        if isinstance(data, list) and data:
            return float(data[-1]["sumOpenInterestValue"])
    except:
        pass
    return None

def binance_delivery_price(symbol: str) -> Optional[float]:
    """Best-effort: use mark price endpoint for delivery contracts if present.
    Delivery symbols on Binance often end with coin pair like BTCUSD_231229 etc. Skipped here for simplicity.
    """
    return None  # оставим для расширения

# ---------- Bybit (perpetual) ----------

def bybit_perp_instruments() -> List[Dict[str, Any]]:
    data = _get(f"{BYBIT_PERP}/v5/market/instruments-info", params={"category": "linear"})
    return data.get("result", {}).get("list", [])

def bybit_funding(symbol: str) -> Optional[float]:
    try:
        data = _get(f"{BYBIT_PERP}/v5/market/funding/history", params={"category": "linear", "symbol": symbol, "limit": 1})
        lst = data.get("result", {}).get("list", [])
        if lst:
            return float(lst[0]["fundingRate"])
    except:
        pass
    return None

def bybit_mark_price(symbol: str) -> Optional[float]:
    try:
        data = _get(f"{BYBIT_PERP}/v5/market/tickers", params={"category": "linear", "symbol": symbol})
        lst = data.get("result", {}).get("list", [])
        if lst:
            return float(lst[0]["markPrice"])
    except:
        pass
    return None

# ---------- OKX ----------

def okx_perp_instruments(instType: str = "SWAP", uly: Optional[str] = None) -> List[Dict[str, Any]]:
    params = {"instType": instType}
    if uly:
        params["uly"] = uly
    data = _get(f"{OKX_BASE}/api/v5/public/instruments", params=params)
    return data.get("data", [])

def okx_ticker(instId: str) -> Optional[Dict[str, Any]]:
    try:
        data = _get(f"{OKX_BASE}/api/v5/market/ticker", params={"instId": instId})
        arr = data.get("data", [])
        if arr:
            return arr[0]
    except:
        pass
    return None

def okx_funding_rate(instId: str) -> Optional[float]:
    try:
        data = _get(f"{OKX_BASE}/api/v5/public/funding-rate", params={"instId": instId})
        arr = data.get("data", [])
        if arr and "fundingRate" in arr[0]:
            return float(arr[0]["fundingRate"])
    except:
        pass
    return None

# ---------- Helpers ----------

def guess_usdt_perp_symbol(base: str) -> List[Tuple[str, str]]:
    """Return list of (venue, symbol) attempts for a base asset (e.g., 'BTC')."""
    candidates = []
    # Binance
    candidates.append(("binance", f"{base.upper()}USDT"))
    # Bybit
    candidates.append(("bybit", f"{base.upper()}USDT"))
    # OKX: SWAP instId looks like BTC-USDT-SWAP
    candidates.append(("okx", f"{base.upper()}-USDT-SWAP"))
    return candidates
