"""
Ejecuta UN solo ciclo de escaneo y termina. Pensado para invocarse desde
GitHub Actions (cron cada 15 min) o cualquier scheduler externo, donde cada
ejecución es un proceso nuevo y corto — a diferencia de auto_scan.py, que
mantiene un proceso corriendo indefinidamente.

Ejecutar con: python run_once.py
"""
import logging

from scan_cycle import load_seen, save_seen, run_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    seen = load_seen()
    seen, total, new_alerts = run_cycle(seen)
    save_seen(seen)
    logger.info(f"Fin del ciclo: {total} candidatos, {new_alerts} alertas nuevas.")


if __name__ == "__main__":
    main()
