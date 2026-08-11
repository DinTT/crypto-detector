"""
Cliente para GeckoTerminal — específicamente el endpoint "new_pools", que
lista pools ordenados por antigüedad REAL de creación (a diferencia de
DexScreener, que solo permite buscar por palabra clave).

Esto es lo que necesitas para capturar tokens como "OpenLiving" (creado hace
2h39m, +92% en 1h) sin depender de que el nombre calce con algún término de
búsqueda fijo.

Docs: https://www.geckoterminal.com/dex-api (endpoint /networks/{network}/new_pools)
No requiere API key para el tier gratuito, pero SÍ tiene rate limit (~30 req/min).

NOTA: este cliente no pudo probarse contra la API real durante el desarrollo
(sin acceso de red en el entorno de construcción). Si los campos no calzan
exactamente con la respuesta real, revisa los logs de GitHub Actions y
ajustamos el parseo.
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.geckoterminal.com/api/v2"

# Mapeo entre los chain IDs que usa DexScreener (los que ya usa el resto del
# proyecto) y los network IDs que usa GeckoTerminal — no siempre son iguales.
CHAIN_ID_MAP = {
    "solana": "solana",
    "bsc": "bsc",
    "ethereum": "eth",
    "base": "base",
}


def get_new_pools(dexscreener_chain_id: str) -> list[dict]:
    """
    Devuelve una lista de pares en el MISMO formato que usa DexScreener
    (compatible con scoring.py), para que el resto del pipeline no tenga que
    cambiar. Convierte la respuesta de GeckoTerminal (formato JSON:API) al
    formato interno esperado.
    """
    network = CHAIN_ID_MAP.get(dexscreener_chain_id)
    if not network:
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/networks/{network}/new_pools",
            params={"page": 1},
            headers={"Accept": "application/json;version=20230302"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Error consultando GeckoTerminal new_pools ({network}): {e}")
        return []
    except ValueError as e:
        logger.warning(f"Respuesta inválida de GeckoTerminal ({network}): {e}")
        return []

    pools = raw.get("data", []) or []
    results = []
    for pool in pools:
        try:
            pair = _convert_pool_to_pair(pool, dexscreener_chain_id)
            if pair:
                results.append(pair)
        except Exception as e:
            # Un pool individual mal formado no debe tumbar todo el escaneo.
            logger.debug(f"Error parseando un pool de GeckoTerminal, se omite: {e}")
            continue

    time.sleep(1.0)  # rate limit conservador (~30/min permitido)
    return results


def _convert_pool_to_pair(pool: dict, chain_id: str) -> dict | None:
    """Convierte un objeto 'pool' de GeckoTerminal al formato interno tipo-DexScreener."""
    attrs = pool.get("attributes", {}) or {}

    name = attrs.get("name", "")  # normalmente "SYMBOL / SOL"
    symbol = name.split("/")[0].strip() if "/" in name else name.strip()
    if not symbol:
        return None

    price_change = attrs.get("price_change_percentage", {}) or {}
    volume = attrs.get("volume_usd", {}) or {}
    txns = attrs.get("transactions", {}) or {}

    def _to_float(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    pool_created_at = attrs.get("pool_created_at")  # ISO string
    created_at_ms = None
    if pool_created_at:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(pool_created_at.replace("Z", "+00:00"))
            created_at_ms = int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            created_at_ms = None

    h1_txns = txns.get("h1", {}) or {}

    return {
        "chainId": chain_id,
        "pairAddress": attrs.get("address", pool.get("id", "")),
        "baseToken": {"symbol": symbol},
        "volume": {
            "h1": _to_float(volume.get("h1")),
            "h24": _to_float(volume.get("h24")),
        },
        "liquidity": {"usd": _to_float(attrs.get("reserve_in_usd"))},
        "marketCap": _to_float(attrs.get("market_cap_usd")) or _to_float(attrs.get("fdv_usd")),
        "fdv": _to_float(attrs.get("fdv_usd")),
        "priceChange": {
            "h1": _to_float(price_change.get("h1")),
            "h6": _to_float(price_change.get("h6")),
            "h24": _to_float(price_change.get("h24")),
        },
        "txns": {
            "h1": {
                "buys": int(_to_float(h1_txns.get("buys"))),
                "sells": int(_to_float(h1_txns.get("sells"))),
            }
        },
        "pairCreatedAt": created_at_ms,
        "url": f"https://www.geckoterminal.com/{CHAIN_ID_MAP.get(chain_id, chain_id)}/pools/{attrs.get('address', '')}",
    }
