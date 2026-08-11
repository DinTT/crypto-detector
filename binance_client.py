"""
Cliente para Binance:
- Símbolos listados (endpoint público, sin credenciales) -> usado en el scanner
  y en la web pública, es información no sensible.
- Balance de cuenta (endpoint autenticado, requiere API key/secret) -> usado
  SOLO localmente en app.py (Streamlit), nunca en el pipeline público de
  GitHub Actions / GitHub Pages.

IMPORTANTE sobre las API keys de Binance:
- Crea una key con SOLO el permiso "Enable Reading" activado.
- NO actives "Enable Spot & Margin Trading" ni "Enable Withdrawals".
  Si alguien llegara a obtener una key de solo lectura, como mucho puede
  ver tu balance — no puede mover ni un centavo.
- Nunca subas tus keys a git. Usa variables de entorno locales.
"""
import hashlib
import hmac
import logging
import time
import urllib.parse

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"


def get_listed_base_assets() -> set[str]:
    """
    Devuelve el set de símbolos base listados en Binance (ej. {"BTC", "ETH", "SOL", ...}).
    Endpoint público, no requiere credenciales. Se usa para chequear si un
    token detectado por el scanner ya cotiza en Binance.
    """
    try:
        resp = requests.get(f"{BASE_URL}/api/v3/exchangeInfo", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        symbols = data.get("symbols", [])
        return {s["baseAsset"].upper() for s in symbols if s.get("status") == "TRADING"}
    except requests.RequestException as e:
        logger.warning(f"Error consultando exchangeInfo de Binance: {e}")
        return set()


def is_listed_on_binance(symbol: str, listed_assets: set[str]) -> bool:
    """Chequea si un símbolo (ej. 'PEPE') está en el set de assets listados."""
    return symbol.upper() in listed_assets


def _signed_get(path: str, api_key: str, api_secret: str, params: dict | None = None) -> dict:
    """Request autenticado con firma HMAC-SHA256, como requiere la API de cuenta de Binance."""
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    query = urllib.parse.urlencode(params)
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    query += f"&signature={signature}"

    url = f"{BASE_URL}{path}?{query}"
    headers = {"X-MBX-APIKEY": api_key}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_account_balances(api_key: str, api_secret: str) -> list[dict]:
    """
    Devuelve el balance de tu cuenta de Binance (solo assets con balance > 0).
    Requiere una API key con permiso de LECTURA únicamente.

    SOLO usar esto localmente (app.py). Nunca en un workflow que corra en
    GitHub Actions ni en código que termine en un repo público.
    """
    if not api_key or not api_secret:
        return []

    try:
        data = _signed_get("/api/v3/account", api_key, api_secret)
    except requests.RequestException as e:
        logger.error(f"Error consultando balance de Binance: {e}")
        return []

    balances = data.get("balances", [])
    result = []
    for b in balances:
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        if free + locked > 0:
            result.append({"asset": b["asset"], "free": free, "locked": locked, "total": free + locked})

    result.sort(key=lambda x: x["total"], reverse=True)
    return result
