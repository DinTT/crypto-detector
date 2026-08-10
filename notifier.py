"""
Envía notificaciones cuando se detecta un token con score alto.
Soporta Telegram (si configuras las credenciales en config.py) o consola como fallback.
"""
import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


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


def notify_digest(token_scores: list) -> None:
    """
    Envía UN mensaje resumen por ciclo con los top candidatos, sin importar
    si superan el umbral de alerta o si ya se notificaron antes. Pensado para
    revisar manualmente el panorama cada 15 min, no solo cuando hay una señal fuerte.
    """
    if not token_scores:
        message = "📊 Escaneo completado — 0 candidatos pasaron los filtros mínimos esta vez."
        _send_telegram(message) or print(message)
        return

    lines = [f"📊 *Top {len(token_scores)} candidatos* (últimos 15 min)\n"]
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
