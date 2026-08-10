"""
Configuración central del Crypto Early Detector (MVP).
Ajusta estos valores según qué tan agresivo/conservador quieras que sea el filtro.
"""
import os

# --- Fuente de datos ---
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex"

# Chains a monitorear (dexscreener soporta muchas; empezamos con las más líquidas)
CHAINS = ["ethereum", "solana", "bsc", "base"]

# --- Filtros mínimos para considerar un token "candidato" ---
# Estos filtros existen para descartar basura antes de gastar tiempo de cómputo/score
MIN_LIQUIDITY_USD = 20_000       # liquidez mínima en el pool
MIN_VOLUME_24H_USD = 50_000      # volumen mínimo en 24h
MIN_PAIR_AGE_HOURS = 2           # evita tokens recién creados (mayor riesgo de rug)
MAX_PAIR_AGE_DAYS = 30           # nos interesa "early", no proyectos ya maduros

# --- Filtro "early stage" ---
# El objetivo es priorizar tokens que están INICIANDO su movimiento, no los que
# ya subieron y están en fase de distribución (ej. MCX en el ejemplo real).
# Un market cap bajo es una proxy imperfecta pero razonable de "todavía no explotó".
MAX_MARKET_CAP_FOR_EARLY = 3_000_000

# Si el cambio de precio en 24h ya es extremo, consideramos que el movimiento
# grande YA OCURRIÓ (no está por ocurrir). Esto veta el score sin importar
# qué tan bien se vean los demás sub-scores.
ALREADY_PUMPED_H24_THRESHOLD = 150   # % de subida en 24h
ROLLOVER_H1_THRESHOLD = -3            # % de caída en 1h que confirma que ya venía bajando

# --- Pesos del score compuesto (deben sumar 1.0) ---
# Score = suma ponderada de sub-scores normalizados 0-100
SCORE_WEIGHTS = {
    "volume_growth": 0.30,   # crecimiento de volumen vs promedio reciente
    "liquidity": 0.20,       # liquidez absoluta y relativa al market cap
    "price_momentum": 0.20,  # variación de precio 1h/6h/24h
    "buy_sell_ratio": 0.15,  # presión compradora vs vendedora
    "volatility_risk": 0.15, # penaliza volatilidad extrema / posible manipulación
}

# --- Umbrales del semáforo ---
SEMAPHORE_THRESHOLDS = {
    "green": 75,   # score >= 75 -> oportunidad interesante, revisar
    "yellow": 50,  # score >= 50 -> esperar confirmación
    # score < 50 -> rojo, alto riesgo / descartar
}

# --- Rate limiting (DexScreener free tier ~300 req/min, seamos conservadores) ---
REQUEST_DELAY_SECONDS = 0.5
MAX_TOKENS_PER_SCAN = 200

# --- Automatización / notificaciones ---
SCAN_INTERVAL_MINUTES = 15
NOTIFY_MIN_SCORE = 70          # ya no filtra las notificaciones, pero se mantiene
                                # por si más adelante quieres volver a un modo selectivo
DIGEST_TOP_N = 7               # cuántos candidatos mostrar en el resumen de cada ciclo
SEEN_TOKENS_DB = "seen_tokens.json"  # ya no bloquea notificaciones, se mantiene por compatibilidad

# Pool amplio de términos de búsqueda. DexScreener no tiene un endpoint de
# "todo lo nuevo en los últimos 15 min", así que dependemos de keywords —
# con un pool fijo chico, terminas viendo siempre los mismos tokens. Rotar
# una muestra distinta cada ciclo ayuda a variar el descubrimiento.
SEARCH_TERMS_POOL = [
    "pepe", "meme", "ai agent", "solana", "doge", "cat", "inu", "moon",
    "based", "elon", "trump", "wojak", "frog", "pump", "bonk", "shib",
    "floki", "ai", "gpt", "agent", "rwa", "defi", "gaming", "layer2",
]
SEARCH_TERMS_PER_SCAN = 6  # cuántos términos del pool usar en cada ciclo

# Telegram (opcional). Se lee primero de variables de entorno (necesario para
# GitHub Actions Secrets) y si no existen, cae al valor hardcodeado de abajo
# (útil para pruebas locales rápidas — pero no subas tu token a un repo público).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or None   # ej: "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or None       # tu chat id numérico
