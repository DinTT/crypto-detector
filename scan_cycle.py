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
from pathlib import Path

from config import NOTIFY_MIN_SCORE, SEEN_TOKENS_DB
from scanner import scan
from notifier import notify

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_TERMS = ["pepe", "ai agent", "meme", "solana"]


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


def run_cycle(seen: set[str]) -> tuple[set[str], int, int]:
    """Corre un ciclo completo. Devuelve (seen_actualizado, total_candidatos, alertas_nuevas)."""
    logger.info("Iniciando escaneo...")
    try:
        results = scan(search_terms=DEFAULT_SEARCH_TERMS, early_stage_only=True)
    except Exception as e:
        logger.error(f"Error durante el escaneo: {e}")
        return seen, 0, 0

    new_alerts = 0
    for r in results:
        if r.total_score < NOTIFY_MIN_SCORE:
            continue
        if r.semaphore == "🔴":
            continue  # el veto de "ya explotó" gana, aunque el score numérico sea alto
        if r.pair_address in seen:
            continue

        notify(r)
        seen.add(r.pair_address)
        new_alerts += 1

    logger.info(f"Escaneo completo. {len(results)} candidatos evaluados, {new_alerts} alertas nuevas.")
    return seen, len(results), new_alerts
