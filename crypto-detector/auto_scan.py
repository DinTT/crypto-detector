"""
Corre el scanner automáticamente cada N minutos (config.SCAN_INTERVAL_MINUTES)
en un LOOP INFINITO dentro del mismo proceso.

Uso: mantener tu PC encendido, o correr en un VPS/servidor con este proceso
persistente (ver systemd/crypto-detector.service para ese caso).

Si en cambio quieres correrlo desde GitHub Actions (sin servidor propio),
usa run_once.py en su lugar — ver DEPLOY.md.

Ejecutar con: python auto_scan.py (Ctrl+C para detener)
"""
import logging
import time

from config import SCAN_INTERVAL_MINUTES
from scan_cycle import load_seen, save_seen, run_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    seen = load_seen()
    logger.info(f"Iniciando auto-scan cada {SCAN_INTERVAL_MINUTES} minutos. Ctrl+C para detener.")

    while True:
        seen, total, new_alerts = run_cycle(seen)
        save_seen(seen)
        time.sleep(SCAN_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
