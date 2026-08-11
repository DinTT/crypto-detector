"""
Lógica de UN ciclo de escaneo: correr scanner.scan(), filtrar por umbral de
notificación, evitar duplicados via seen_tokens.json, y notificar.

Compartido entre:
- auto_scan.py: lo llama en loop infinito (uso local / VPS con proceso persistente)
- run_once.py: lo llama una sola vez (uso en GitHub Actions / cron, donde cada
  ejecución es un proceso nuevo)
"""
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from config import (
    NOTIFY_MIN_SCORE,
    SEEN_TOKENS_DB,
    DIGEST_TOP_N,
    SEARCH_TERMS_POOL,
    SEARCH_TERMS_PER_SCAN,
    LATEST_SCAN_JSON,
)
from scanner import scan
from notifier import notify, notify_digest, notify_error
from binance_client import get_listed_base_assets, is_listed_on_binance

logger = logging.getLogger(__name__)


def load_seen() -> set[str]:
    path = Path(SEEN_TOKENS_DB)
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen: set[str]) -> None:
    Path(SEEN_TOKENS_DB).write_text(json.dumps(sorted(seen)))


def _pair_age_hours(raw: dict) -> float | None:
    created_at = raw.get("pairCreatedAt")
    if not created_at:
        return None
    created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
    return (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600


def save_latest_results(results: list) -> None:
    """
    Guarda TODOS los resultados del ciclo (no solo el top N del digest) en un
    JSON que consume la página web móvil (docs/index.html vía GitHub Pages).
    Se sobreescribe en cada ciclo — no es un histórico, es "el estado actual".

    Incluye si cada token ya está listado en Binance (chequeo público, sin
    credenciales) — pero NUNCA balance de cuenta, eso queda solo local.
    """
    listed_assets = get_listed_base_assets()

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tokens": [
            {
                "symbol": r.symbol,
                "chain": r.chain,
                "pair_address": r.pair_address,
                "score": r.total_score,
                "semaphore": r.semaphore,
                "sub_scores": r.sub_scores,
                "reasons": r.reasons,
                "url": r.raw.get("url", ""),
                "age_hours": _pair_age_hours(r.raw),
                "liquidity_usd": (r.raw.get("liquidity") or {}).get("usd"),
                "market_cap": r.raw.get("marketCap") or r.raw.get("fdv"),
                "price_change_24h": (r.raw.get("priceChange") or {}).get("h24"),
                "on_binance": is_listed_on_binance(r.symbol, listed_assets),
            }
            for r in results
        ],
    }
    path = Path(LATEST_SCAN_JSON)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def pick_search_terms() -> list[str]:
    """Elige una muestra aleatoria del pool de términos en cada ciclo, para
    variar el descubrimiento en vez de buscar siempre exactamente lo mismo."""
    pool = SEARCH_TERMS_POOL
    n = min(SEARCH_TERMS_PER_SCAN, len(pool))
    return random.sample(pool, n)


def run_cycle(seen: set[str]) -> tuple[set[str], int, int]:
    """Corre un ciclo completo. Devuelve (seen_actualizado, total_candidatos, alertas_nuevas)."""
    search_terms = pick_search_terms()
    logger.info(f"Iniciando escaneo con términos: {search_terms}")
    try:
        results = scan(search_terms=search_terms, early_stage_only=True)
    except Exception as e:
        logger.error(f"Error durante el escaneo: {e}")
        notify_error(f"El escaneo falló con este error:\n`{e}`")
        return seen, 0, 0

    # Resumen SIEMPRE se envía, sin importar score — para revisar el panorama
    # completo cada ciclo en vez de solo enterarte de señales "fuertes".
    try:
        notify_digest(results[:DIGEST_TOP_N])
    except Exception as e:
        logger.error(f"Error enviando el digest: {e}")
        notify_error(f"El escaneo funcionó ({len(results)} candidatos) pero falló al enviar el resumen:\n`{e}`")

    # Guarda TODOS los resultados para la página web móvil (docs/index.html)
    try:
        save_latest_results(results)
    except Exception as e:
        logger.error(f"Error guardando resultados para la web: {e}")

    # Además, marca cuáles fueron señales fuertes nuevas (para no perder esa
    # distinción si más adelante quieres volver a un modo más selectivo).
    new_alerts = 0
    for r in results:
        if r.total_score < NOTIFY_MIN_SCORE:
            continue
        if r.semaphore == "🔴":
            continue
        if r.pair_address in seen:
            continue
        seen.add(r.pair_address)
        new_alerts += 1

    logger.info(f"Escaneo completo. {len(results)} candidatos evaluados, {new_alerts} eran señales fuertes nuevas.")
    return seen, len(results), new_alerts
