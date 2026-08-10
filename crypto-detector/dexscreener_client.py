"""
Cliente simple para la API pública de DexScreener.
No requiere API key. Docs: https://docs.dexscreener.com/api/reference

IMPORTANTE: este archivo hace requests HTTP reales. Pruébalo en tu máquina local,
no en un sandbox sin salida de red.
"""
import time
import logging
from typing import Optional

import requests

from config import DEXSCREENER_BASE_URL, REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)


class DexScreenerClient:
    def __init__(self, base_url: str = DEXSCREENER_BASE_URL, delay: float = REQUEST_DELAY_SECONDS):
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            time.sleep(self.delay)  # rate limit básico
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"Error consultando {url}: {e}")
            return None

    def search_pairs(self, query: str) -> list[dict]:
        """Busca pares por nombre/símbolo/dirección de contrato."""
        data = self._get("/search", params={"q": query})
        if not data:
            return []
        return data.get("pairs", []) or []

    def get_pairs_by_chain_and_address(self, chain: str, pair_address: str) -> Optional[dict]:
        """Obtiene detalle de un par específico."""
        data = self._get(f"/pairs/{chain}/{pair_address}")
        if not data:
            return None
        pairs = data.get("pairs") or []
        return pairs[0] if pairs else None

    def get_token_pairs(self, chain: str, token_address: str) -> list[dict]:
        """Obtiene todos los pares (pools) donde aparece un token."""
        data = self._get(f"/tokens/{token_address}")
        if not data:
            return []
        pairs = data.get("pairs", []) or []
        return [p for p in pairs if p.get("chainId") == chain]

    def get_boosted_tokens(self) -> list[dict]:
        """
        Tokens con "boost"/trending reciente. Este endpoint vive en un base_url distinto
        al resto (no bajo /latest/dex), así que hace su propia request directa.
        Verifica siempre contra la documentación actual antes de depender de esto en producción,
        ya que endpoints no versionados de DexScreener pueden cambiar sin aviso.
        """
        url = "https://api.dexscreener.com/token-boosts/latest/v1"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            time.sleep(self.delay)
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as e:
            logger.warning(f"Error consultando {url}: {e}")
            return []
