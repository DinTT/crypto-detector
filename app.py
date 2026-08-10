"""
Crypto Early Detector — MVP (Fase 1: scoring heurístico, sin ML)

Ejecutar con: streamlit run app.py
"""
import logging

import streamlit as st
import pandas as pd

from scanner import scan
from config import SEMAPHORE_THRESHOLDS

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Crypto Early Detector", page_icon="🚨", layout="wide")

st.title("🚨 Crypto Early Detector — MVP")
st.caption(
    "Fase 1: scoring heurístico basado en volumen, liquidez, momentum y presión "
    "compradora. Sin Machine Learning todavía — eso viene en la Fase 2, una vez "
    "que el pipeline de datos esté validado."
)

with st.sidebar:
    st.header("Configuración del escaneo")
    search_input = st.text_input(
        "Términos de búsqueda (separados por coma)",
        value="pepe, ai agent, meme",
        help="DexScreener no expone 'todos los tokens nuevos' directamente; "
             "usamos búsquedas por término + tokens con boost como fuente de candidatos.",
    )
    early_stage = st.checkbox(
        "Solo tokens 'early stage' (market cap bajo)",
        value=True,
        help="Excluye tokens que ya tuvieron su movimiento grande (ej. market cap "
             "ya alto). Prioriza detectar el inicio de un movimiento, no confirmar "
             "uno que ya se ve claramente en el gráfico.",
    )
    run_scan = st.button("🔍 Ejecutar escaneo", type="primary")

    st.divider()
    st.caption("Umbrales actuales")
    st.write(f"🟢 Score ≥ {SEMAPHORE_THRESHOLDS['green']}")
    st.write(f"🟡 Score ≥ {SEMAPHORE_THRESHOLDS['yellow']}")
    st.write("🔴 Score menor — alto riesgo")

if "results" not in st.session_state:
    st.session_state.results = []

if run_scan:
    terms = [t.strip() for t in search_input.split(",") if t.strip()]
    with st.spinner("Escaneando DexScreener... esto puede tardar según el número de candidatos."):
        try:
            st.session_state.results = scan(search_terms=terms, early_stage_only=early_stage)
        except Exception as e:
            st.error(f"Error durante el escaneo: {e}")
            st.session_state.results = []

results = st.session_state.results

if not results:
    st.info("Ejecuta un escaneo desde la barra lateral para ver resultados.")
else:
    st.success(f"{len(results)} tokens pasaron los filtros mínimos y fueron evaluados.")

    rows = []
    for r in results:
        rows.append({
            "Semáforo": r.semaphore,
            "Símbolo": r.symbol,
            "Chain": r.chain,
            "Score": r.total_score,
            "Volumen↑": r.sub_scores.get("volume_growth"),
            "Liquidez": r.sub_scores.get("liquidity"),
            "Momentum": r.sub_scores.get("price_momentum"),
            "Compra/Venta": r.sub_scores.get("buy_sell_ratio"),
            "Riesgo Vol.": r.sub_scores.get("volatility_risk"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Detalle por token")
    for r in results[:20]:  # limitar detalle a top 20 para no saturar la UI
        with st.expander(f"{r.semaphore} {r.symbol} — Score {r.total_score}/100 ({r.chain})"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Sub-scores:**")
                for k, v in r.sub_scores.items():
                    st.write(f"- {k}: {v}")
            with col2:
                st.write("**Motivos destacados:**")
                if r.reasons:
                    for reason in r.reasons:
                        st.write(f"✓ {reason}")
                else:
                    st.write("Sin señales destacadas (score moderado, sin banderas fuertes).")

            pair_url = r.raw.get("url")
            if pair_url:
                st.markdown(f"[Ver en DexScreener]({pair_url})")

st.divider()
st.caption(
    "⚠️ Esto es una herramienta de filtrado, no una recomendación de inversión. "
    "Ningún score garantiza rentabilidad. Verifica siempre manualmente antes de operar: "
    "contrato, auditoría, equipo, y liquidez bloqueada."
)
