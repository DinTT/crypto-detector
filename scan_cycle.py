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
from pathlib import Path

from config import NOTIFY_MIN_SCORE, SEEN_TOKENS_DB, DIGEST_TOP_N, SEARCH_TERMS_POOL, SEARCH_TERMS_PER_SCAN
from scanner import scan
from notifier import notify, notify_digest

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
        return seen, 0, 0

    # Resumen SIEMPRE se envía, sin importar score — para revisar el panorama
    # completo cada ciclo en vez de solo enterarte de señales "fuertes".
    notify_digest(results[:DIGEST_TOP_N])

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
