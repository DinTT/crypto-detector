"""
Scoring compuesto para el MVP (sin ML todavía).
Toma un "pair" de DexScreener (dict) y devuelve un score 0-100 + desglose.

Esto es intencionalmente heurístico y simple: el objetivo de esta primera fase
es validar que el pipeline de datos funciona y que el score ordena los tokens
de forma razonable, antes de meter un modelo entrenado encima.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import (
    SCORE_WEIGHTS,
    SEMAPHORE_THRESHOLDS,
    ALREADY_PUMPED_H24_THRESHOLD,
    ROLLOVER_H1_THRESHOLD,
)


@dataclass
class TokenScore:
    symbol: str
    chain: str
    pair_address: str
    total_score: float
    semaphore: str
    sub_scores: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def score_volume_growth(pair: dict) -> tuple[float, str]:
    """Compara volumen 1h vs 24h para estimar aceleración reciente."""
    vol = pair.get("volume", {}) or {}
    vol_1h = vol.get("h1", 0) or 0
    vol_24h = vol.get("h24", 0) or 0

    if vol_24h <= 0:
        return 0.0, ""

    # Volumen promedio por hora en las últimas 24h
    avg_hourly = vol_24h / 24
    if avg_hourly <= 0:
        return 0.0, ""

    ratio = vol_1h / avg_hourly  # >1 significa que la última hora está por encima del promedio
    # Mapeo: ratio 1x -> 30, ratio 3x -> 70, ratio 6x+ -> 100
    score = _clamp(20 + ratio * 15)
    reason = ""
    if ratio >= 3:
        reason = f"Volumen última hora {ratio:.1f}x el promedio de 24h"
    return score, reason


def score_liquidity(pair: dict) -> tuple[float, str]:
    """Evalúa liquidez absoluta y relación liquidez/market cap (evita pools trampa)."""
    liquidity_usd = (pair.get("liquidity") or {}).get("usd", 0) or 0
    market_cap = pair.get("marketCap") or pair.get("fdv") or 0

    # Score base por liquidez absoluta (escala logarítmica aproximada)
    if liquidity_usd <= 0:
        base = 0
    elif liquidity_usd < 20_000:
        base = 10
    elif liquidity_usd < 100_000:
        base = 40
    elif liquidity_usd < 500_000:
        base = 70
    else:
        base = 90

    reason = ""
    # Penaliza si la liquidez es sospechosamente baja respecto al market cap
    # (puede indicar facilidad para manipular el precio)
    if market_cap and liquidity_usd:
        ratio = liquidity_usd / market_cap
        if ratio < 0.02:
            base *= 0.5
            reason = "Liquidez muy baja respecto al market cap (riesgo de manipulación)"

    return _clamp(base), reason


def score_price_momentum(pair: dict) -> tuple[float, str]:
    """Combina variación de precio en 1h, 6h y 24h."""
    change = pair.get("priceChange", {}) or {}
    h1 = change.get("h1", 0) or 0
    h6 = change.get("h6", 0) or 0
    h24 = change.get("h24", 0) or 0

    # Momentum positivo sostenido (no solo un pico de 1h) puntúa más
    weighted = (h1 * 0.5) + (h6 * 0.3) + (h24 * 0.2)
    score = _clamp(50 + weighted * 1.2)

    reason = ""
    if h1 > 15 and h6 > 10:
        reason = f"Momentum sostenido: +{h1:.0f}% (1h), +{h6:.0f}% (6h)"
    return score, reason


def score_buy_sell_ratio(pair: dict) -> tuple[float, str]:
    """Presión compradora vs vendedora en la última hora."""
    txns = (pair.get("txns") or {}).get("h1", {}) or {}
    buys = txns.get("buys", 0) or 0
    sells = txns.get("sells", 0) or 0
    total = buys + sells

    if total == 0:
        return 30.0, ""  # sin actividad = neutral-bajo, no penalizamos fuerte

    buy_ratio = buys / total
    score = _clamp(buy_ratio * 100)

    reason = ""
    if buy_ratio > 0.65 and total > 20:
        reason = f"Presión compradora fuerte: {buys} compras vs {sells} ventas (última hora)"
    return score, reason


def score_volatility_risk(pair: dict) -> tuple[float, str]:
    """
    Penaliza volatilidad extrema, que suele preceder a rug pulls o pump-and-dumps.
    Score alto = bajo riesgo (menos volátil de forma errática).
    """
    change = pair.get("priceChange", {}) or {}
    h1 = abs(change.get("h1", 0) or 0)
    h24 = abs(change.get("h24", 0) or 0)

    reason = ""
    if h1 > 50:
        # movimiento extremo en 1 hora: alta probabilidad de manipulación o evento anómalo
        score = 15.0
        reason = f"Volatilidad extrema en 1h ({h1:.0f}%), posible manipulación"
    elif h24 > 200:
        score = 25.0
        reason = f"Volatilidad extrema en 24h ({h24:.0f}%)"
    else:
        # menos volátil relativo = más score, pero no queremos premiar cero movimiento
        score = _clamp(80 - h1)

    return _clamp(score), reason


def detect_already_pumped(pair: dict) -> str | None:
    """
    Detecta el patrón "el movimiento grande ya ocurrió y está en distribución":
    subida extrema en 24h + caída en la última hora (el "rollover" post-pico).
    Esto es exactamente lo que le pasaba a MCX cuando salió con score 71.4 —
    ya había subido 2125% y estaba bajando desde el máximo.

    Devuelve un string con el motivo del veto, o None si no aplica.
    """
    change = pair.get("priceChange", {}) or {}
    h1 = change.get("h1", 0) or 0
    h24 = change.get("h24", 0) or 0

    if h24 >= ALREADY_PUMPED_H24_THRESHOLD and h1 <= ROLLOVER_H1_THRESHOLD:
        return (
            f"Movimiento grande YA OCURRIÓ (+{h24:.0f}% en 24h) y ahora está "
            f"bajando ({h1:.0f}% última hora) — fase de distribución, no de entrada"
        )
    return None


def compute_score(pair: dict) -> TokenScore:
    """Calcula el score compuesto final para un par de DexScreener."""
    sub_scores = {}
    reasons = []

    veto_reason = detect_already_pumped(pair)

    functions = {
        "volume_growth": score_volume_growth,
        "liquidity": score_liquidity,
        "price_momentum": score_price_momentum,
        "buy_sell_ratio": score_buy_sell_ratio,
        "volatility_risk": score_volatility_risk,
    }

    total = 0.0
    for key, func in functions.items():
        s, reason = func(pair)
        sub_scores[key] = round(s, 1)
        total += s * SCORE_WEIGHTS[key]
        if reason:
            reasons.append(reason)

    total = round(_clamp(total), 1)

    if veto_reason:
        # El veto gana siempre, sin importar qué tan bien se vean los sub-scores.
        semaphore = "🔴"
        reasons.insert(0, veto_reason)
    elif total >= SEMAPHORE_THRESHOLDS["green"]:
        semaphore = "🟢"
    elif total >= SEMAPHORE_THRESHOLDS["yellow"]:
        semaphore = "🟡"
    else:
        semaphore = "🔴"

    base_token = pair.get("baseToken", {}) or {}

    return TokenScore(
        symbol=base_token.get("symbol", "?"),
        chain=pair.get("chainId", "?"),
        pair_address=pair.get("pairAddress", "?"),
        total_score=total,
        semaphore=semaphore,
        sub_scores=sub_scores,
        reasons=reasons,
        raw=pair,
    )
