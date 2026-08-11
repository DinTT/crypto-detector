"""
Envía notificaciones cuando se detecta un token con score alto.
Soporta Telegram (si configuras las credenciales en config.py) o consola como fallback.
"""
import logging
from datetime import datetime, timezone

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _format_age(pair: dict) -> str:
    """Devuelve la edad del par en formato legible (ej. '18 min', '3.5h')."""
    created_at = pair.get("pairCreatedAt")
    if not created_at:
        return "edad desconocida"
    created_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
    delta_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
    if delta_hours < 1:
        return f"{int(delta_hours * 60)} min"
    return f"{delta_hours:.1f}h"


def _send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Error enviando notificación a Telegram: {e}")
        return False


def notify_error(message: str) -> None:
    """Notifica cuando el escaneo falla, para que sepas que hubo un problema
    en vez de simplemente no recibir mensaje y no saber por qué."""
    text = f"⚠️ *Error en el escaneo*\n\n{message}\n\nEl próximo ciclo lo reintenta automáticamente."
    sent = _send_telegram(text)
    if not sent:
        print(f"\n⚠️ ERROR: {message}")


def notify(token_score) -> None:
    """Recibe un TokenScore y lo notifica por el canal configurado."""
    reasons_text = "\n".join(f"✓ {r}" for r in token_score.reasons) or "Sin motivos destacados"

    message = (
        f"🚨 *{token_score.symbol}* ({token_score.chain})\n"
        f"Score: *{token_score.total_score}/100* {token_score.semaphore}\n\n"
        f"{reasons_text}\n\n"
        f"{token_score.raw.get('url', '')}"
    )

    sent = _send_telegram(message)
    if not sent:
        # Fallback: consola. Útil también para debug aunque tengas Telegram configurado.
        print("\n" + "=" * 60)
        print(message.replace("*", ""))
        print("=" * 60)


def notify_digest(token_scores: list, young_scores: list | None = None) -> None:
    """
    Envía UN mensaje resumen por ciclo con los top candidatos por score, y
    opcionalmente una sección aparte de tokens RECIÉN CREADOS (sin importar
    su score) — porque tokens con minutos de vida suelen puntuar bajo por la
    penalización de volatilidad, pero son justo los que interesan para una
    estrategia de entrar apenas nace el token.
    """
    if not token_scores and not young_scores:
        message = "📊 Escaneo completado — 0 candidatos pasaron los filtros mínimos esta vez."
        _send_telegram(message) or print(message)
        return

    lines = []

    if young_scores:
        lines.append(f"🆕 *Recién creados* (< 1h de vida)\n")
        for r in young_scores:
            reason = r.reasons[0] if r.reasons else "sin señales destacadas"
            lines.append(
                f"{r.semaphore} *{r.symbol}* ({r.chain}) — {r.total_score}/100\n"
                f"   {reason}\n"
                f"   {r.raw.get('url', '')}"
            )
        lines.append("")  # separador

    if token_scores:
        lines.append(f"📊 *Top {len(token_scores)} por score* (últimos ciclos)\n")
        for r in token_scores:
            reason = r.reasons[0] if r.reasons else "sin señales destacadas"
            lines.append(
                f"{r.semaphore} *{r.symbol}* ({r.chain}) — {r.total_score}/100\n"
                f"   {reason}\n"
                f"   {r.raw.get('url', '')}"
            )

    message = "\n".join(lines)

    # Telegram limita mensajes a 4096 caracteres; recortamos por seguridad
    if len(message) > 4000:
        message = message[:3980] + "\n\n(...) mensaje recortado"

    sent = _send_telegram(message)
    if not sent:
        print("\n" + "=" * 60)
        print(message.replace("*", ""))
        print("=" * 60)
