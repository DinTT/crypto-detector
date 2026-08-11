"""
Orquesta: búsqueda de pares candidatos -> filtros mínimos -> scoring -> ranking.

Nota sobre la fuente de candidatos: DexScreener no tiene un endpoint único de
"todos los tokens nuevos". Este MVP usa search_pairs con términos configurables
y get_boosted_tokens como fuentes de candidatos. Para producción conviene
combinar esto con otras fuentes (ej. GeckoTerminal "new pools" endpoint).
"""
import logging
from datetime import datetime, timezone

from config import (
    CHAINS,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    MIN_PAIR_AGE_HOURS,
    MAX_PAIR_AGE_DAYS,
    MAX_TOKENS_PER_SCAN,
    MAX_MARKET_CAP_FOR_EARLY,
)
from dexscreener_client import DexScreenerClient
from geckoterminal_client import get_new_pools
from scoring import compute_score, TokenScore

logger = logging.getLogger(__name__)


def _pair_age_hours(pair: dict) -> float | None:
    created_at = pair.get("pairCreatedAt")
    if not created_at:
        return None
    created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
    delta = datetime.now(timezone.utc) - created_dt
    return delta.total_seconds() / 3600


def passes_filters(pair: dict) -> bool:
    if pair.get("chainId") not in CHAINS:
        return False

    liquidity_usd = (pair.get("liquidity") or {}).get("usd", 0) or 0
    if liquidity_usd < MIN_LIQUIDITY_USD:
        return False

    volume_24h = (pair.get("volume") or {}).get("h24", 0) or 0
    if volume_24h < MIN_VOLUME_24H_USD:
        return False

    age_hours = _pair_age_hours(pair)
    if age_hours is not None:
        if age_hours < MIN_PAIR_AGE_HOURS:
            return False
        if age_hours > MAX_PAIR_AGE_DAYS * 24:
            return False

    return True


def is_early_stage(pair: dict) -> bool:
    """
    Filtro adicional (opcional) para priorizar tokens que todavía no
    tuvieron su movimiento grande, en vez de tokens ya "explotados".
    Úsalo cuando el objetivo es detectar temprano, no confirmar un pump ya visible.
    """
    market_cap = pair.get("marketCap") or pair.get("fdv") or 0
    if market_cap <= 0:
        return False  # sin dato de market cap, no podemos confirmar que es "early"
    return market_cap <= MAX_MARKET_CAP_FOR_EARLY


def collect_candidate_pairs(client: DexScreenerClient, search_terms: list[str]) -> list[dict]:
    """Reúne candidatos desde boosted tokens + búsquedas por término + "new pools"
    de GeckoTerminal, deduplicando por pairAddress.

    La fuente de GeckoTerminal es la más importante para capturar tokens
    recién creados que NO calzan con ningún término de búsqueda fijo (ej.
    un token nuevo con nombre random que nunca vas a adivinar como keyword).
    """
    seen = {}

    for item in client.get_boosted_tokens():
        token_address = item.get("tokenAddress")
        chain = item.get("chainId")
        if not token_address or not chain:
            continue
        for pair in client.get_token_pairs(chain, token_address):
            seen[pair.get("pairAddress")] = pair

    for term in search_terms:
        for pair in client.search_pairs(term):
            seen[pair.get("pairAddress")] = pair

    for chain in CHAINS:
        for pair in get_new_pools(chain):
            addr = pair.get("pairAddress")
            if addr and addr not in seen:
                seen[addr] = pair

    return list(seen.values())[:MAX_TOKENS_PER_SCAN]


def scan(search_terms: list[str] | None = None, early_stage_only: bool = False) -> list[TokenScore]:
    """Ejecuta un escaneo completo y devuelve resultados ordenados por score descendente.

    early_stage_only=True aplica el filtro de market cap bajo, para priorizar
    tokens que todavía no tuvieron su movimiento grande (en vez de confirmar
    pumps que ya ocurrieron, como pasaba con MCX).
    """
    client = DexScreenerClient()
    search_terms = search_terms or []

    candidates = collect_candidate_pairs(client, search_terms)
    logger.info(f"Candidatos recolectados: {len(candidates)}")

    filtered = [p for p in candidates if passes_filters(p)]
    if early_stage_only:
        filtered = [p for p in filtered if is_early_stage(p)]
    logger.info(f"Candidatos tras filtros mínimos: {len(filtered)}")

    scored = [compute_score(p) for p in filtered]
    scored.sort(key=lambda ts: ts.total_score, reverse=True)

    return scored
