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
