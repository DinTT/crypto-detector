"""
Prueba la lógica de scoring con pares simulados (sin llamadas de red).
Ejecutar con: python test_scoring_mock.py
"""
from scoring import compute_score

# Caso 1: token con señales fuertes y "sanas" (esperamos score alto, verde)
strong_healthy = {
    "chainId": "solana",
    "pairAddress": "0xAAA",
    "baseToken": {"symbol": "STRONG"},
    "volume": {"h1": 50_000, "h24": 300_000},
    "liquidity": {"usd": 400_000},
    "marketCap": 2_000_000,
    "priceChange": {"h1": 12, "h6": 25, "h24": 40},
    "txns": {"h1": {"buys": 180, "sells": 60}},
    "url": "https://dexscreener.com/solana/0xAAA",
}

# Caso 2: pump sospechoso (volatilidad extrema, poca liquidez vs market cap -> riesgo)
suspicious_pump = {
    "chainId": "bsc",
    "pairAddress": "0xBBB",
    "baseToken": {"symbol": "SUSP"},
    "volume": {"h1": 20_000, "h24": 40_000},
    "liquidity": {"usd": 15_000},
    "marketCap": 5_000_000,
    "priceChange": {"h1": 85, "h6": 120, "h24": 300},
    "txns": {"h1": {"buys": 10, "sells": 8}},
    "url": "https://dexscreener.com/bsc/0xBBB",
}

# Caso 3: token estable sin señales particulares (esperamos score medio-bajo)
neutral = {
    "chainId": "ethereum",
    "pairAddress": "0xCCC",
    "baseToken": {"symbol": "MEH"},
    "volume": {"h1": 5_000, "h24": 120_000},
    "liquidity": {"usd": 80_000},
    "marketCap": 1_000_000,
    "priceChange": {"h1": 0.5, "h6": -1, "h24": 2},
    "txns": {"h1": {"buys": 15, "sells": 14}},
    "url": "https://dexscreener.com/ethereum/0xCCC",
}

cases = [strong_healthy, suspicious_pump, neutral]

print(f"{'Símbolo':<10}{'Score':<8}{'Semáforo':<10}Sub-scores")
print("-" * 80)
for pair in cases:
    result = compute_score(pair)
    print(f"{result.symbol:<10}{result.total_score:<8}{result.semaphore:<10}{result.sub_scores}")
    if result.reasons:
        for r in result.reasons:
            print(f"    - {r}")

# Aserciones básicas de sanity check
assert compute_score(strong_healthy).total_score > compute_score(neutral).total_score, \
    "El token con señales fuertes debería puntuar más que el neutral"
assert compute_score(suspicious_pump).sub_scores["volatility_risk"] < 30, \
    "El pump sospechoso debería tener score de riesgo bajo (= alto riesgo detectado)"

print("\n✅ Todos los sanity checks pasaron.")
