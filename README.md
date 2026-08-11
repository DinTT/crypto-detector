# Crypto Early Detector — MVP (Fase 1)

Scoring heurístico de tokens cripto basado en volumen, liquidez, momentum de precio
y presión compradora, usando datos gratuitos de DexScreener. **Sin Machine Learning
todavía** — esta fase existe para validar el pipeline de datos antes de invertir
tiempo en un modelo entrenado.

## ⚠️ Antes de usar

Esto es una herramienta de **filtrado**, no de predicción. Ningún score garantiza
rentabilidad y el mercado cripto es altamente manipulable (wash trading, bots,
whales coordinando). Trátalo como un primer filtro, no como una señal de compra.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Validar la lógica de scoring (sin red)

```bash
python test_scoring_mock.py
```

Esto corre 3 casos simulados (token sano, pump sospechoso, token neutral) y
verifica que el ranking tenga sentido. Últimos resultados observados:

- `STRONG` (señales sanas): score ~75, 🟡
- `SUSP` (pump con liquidez baja): score ~62, 🟡 — **detectado como riesgoso en
  el desglose, pero el score total no baja tanto como debería**. Es una
  limitación conocida: el momentum extremo sigue pesando fuerte aunque
  `volatility_risk` lo penalice. Si te encuentras con esto en producción,
  considera bajar el peso de `price_momentum` o subir el de `volatility_risk`
  en `config.py`, o aplicar un cap duro (ej. "si volatility_risk < 20, forzar
  semáforo rojo sin importar el resto").
- `MEH` (sin señales): score ~48, 🔴

## Automatizar (escaneo cada 15 min + notificaciones)

```bash
python auto_scan.py
```

Corre indefinidamente (Ctrl+C para detener), escaneando cada `SCAN_INTERVAL_MINUTES`
(default 15, ajustable en `config.py`). Solo notifica tokens con:
- Score >= `NOTIFY_MIN_SCORE` (default 70)
- Semáforo distinto de 🔴 (el veto de "ya explotó" siempre gana)
- Que no se hayan notificado antes (se guarda en `seen_tokens.json` para no
  repetir alertas del mismo token)

**Notificaciones**: por defecto se imprimen en consola. Para recibirlas en
Telegram, crea un bot con [@BotFather](https://t.me/BotFather), obtén tu
`chat_id` (puedes usar [@userinfobot](https://t.me/userinfobot)), y completa
`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` en `config.py`.

**Para dejarlo corriendo 24/7** sin mantener la terminal abierta, en Windows
puedes usar el Programador de tareas para ejecutar el script al iniciar sesión,
o correrlo en un servidor pequeño (ej. una VPS barata) si no quieres depender
de que tu computador esté siempre prendido.

## Sobre el filtro "early stage" y el veto anti-pump

Después de ver el caso real de MCX (score 71.4 cuando ya había subido 2125%
y estaba en fase de distribución/bajada), se agregaron dos mecanismos:

1. **`is_early_stage()`** (activable con `early_stage_only=True`): descarta
   tokens con market cap por encima de `MAX_MARKET_CAP_FOR_EARLY` — la idea es
   priorizar tokens que probablemente *todavía no* tuvieron su movimiento grande.
2. **`detect_already_pumped()`**: si un token subió más de
   `ALREADY_PUMPED_H24_THRESHOLD`% en 24h Y está cayendo en la última hora,
   se fuerza el semáforo a 🔴 sin importar el score numérico — es la firma de
   "el pico ya pasó".

Estos dos filtros reducen falsos positivos tipo MCX, pero **no eliminan el
riesgo de entrar temprano en algo que resulta ser un rug pull** o que nunca
despega. Un market cap bajo también describe a la inmensa mayoría de tokens
que fracasan.

## Balance de Binance (opcional, solo local)

Esto **nunca corre en GitHub Actions ni en la web pública** — solo en tu PC,
cuando ejecutas `streamlit run app.py` manualmente.

### Crear una API key de SOLO LECTURA

1. Entra a Binance → perfil → **API Management**.
2. Crea una nueva API key.
3. **CRÍTICO**: en los permisos, deja activado únicamente **"Enable Reading"**.
   Deja DESACTIVADOS "Enable Spot & Margin Trading" y "Enable Withdrawals".
   Con una key de solo lectura, aunque alguien la obtenga, no puede mover tu
   dinero — solo ver el balance.
4. Guarda el API Key y el Secret Key que te entrega Binance (el secret solo
   se muestra una vez).

### Configurar las credenciales localmente

**Nunca las pongas directamente en el código ni las subas a git.** Configúralas
como variables de entorno antes de correr la app:

En Windows (PowerShell), cada vez que abras una terminal nueva antes de correr la app:

```powershell
$env:BINANCE_API_KEY="tu_api_key_aqui"
$env:BINANCE_API_SECRET="tu_secret_key_aqui"
streamlit run app.py
```

Luego, en el dashboard, baja hasta la sección "💰 Balance de Binance" y click
en "Consultar balance".

## Chequeo de "¿está en Binance?"

A diferencia del balance, esto SÍ corre en el pipeline automático (GitHub
Actions) porque usa el endpoint público de Binance (sin credenciales) —
no es información sensible. Cada token en el digest y en la web móvil
muestra un badge amarillo "Binance" si ya cotiza ahí.

**Nota realista**: la gran mayoría de tokens que detecta este scanner
(memecoins nuevos en Solana/BSC/Base) NO están listados en Binance, porque
Binance solo lista tokens que pasan su propio proceso de aprobación. Es
normal ver el badge "Binance" en muy pocos o ningún candidato.

## Ejecutar el dashboard

```bash
streamlit run app.py
```

Escribe términos de búsqueda en la barra lateral (DexScreener no tiene un
endpoint de "todos los tokens nuevos", así que este MVP combina tokens con
boost + búsquedas por término como fuente de candidatos) y pulsa "Ejecutar
escaneo".

## Estructura

```
config.py               # umbrales, pesos del score, chains a monitorear
dexscreener_client.py   # wrapper de la API pública de DexScreener
scoring.py               # lógica de scoring compuesto (5 sub-scores)
scanner.py                # filtros mínimos + orquestación
app.py                     # dashboard Streamlit
test_scoring_mock.py    # validación sin red
```

## Ajustar el comportamiento

Todo lo importante está en `config.py`:

- `MIN_LIQUIDITY_USD`, `MIN_VOLUME_24H_USD`: filtros de entrada antes de
  siquiera calcular el score.
- `SCORE_WEIGHTS`: pesos de cada sub-score (deben sumar 1.0).
- `SEMAPHORE_THRESHOLDS`: a partir de qué score se considera 🟢/🟡/🔴.

## Qué falta para Fase 2 (ML)

Una vez que hayas corrido el scanner unos días y tengas sensación de qué tan
bien (o mal) rankea el score heurístico:

1. **Recolectar histórico**: guardar snapshots del scanner cada X minutos en
   una base de datos (SQLite sirve para empezar) para tener series de tiempo
   por token.
2. **Etiquetar outcomes**: para cada token, ¿qué pasó 24h/7d después del
   snapshot? (subió, bajó, fue rug pull).
3. **Entrenar un modelo simple** (XGBoost/LightGBM) sobre esas features +
   outcome, en vez de los pesos fijos actuales.
4. **Backtesting** antes de confiar en cualquier output — separar datos de
   entrenamiento y de prueba por *tiempo*, no aleatoriamente, para evitar
   data leakage (es un error muy común en este tipo de proyectos).

## Fuentes de datos adicionales a considerar más adelante

- **On-chain real** (holders, concentración de wallets): DexScreener no lo
  expone. Necesitarías Etherscan/Solscan API o servicios como Nansen/Arkham
  (de pago para datos de whales confiables).
- **Sentimiento social**: Twitter/X API es cara ahora; alternativas más
  económicas incluyen scraping de Telegram/Discord públicos (revisa términos
  de servicio) o LunarCrush.
- **Seguridad de contratos** (rug pull risk, honeypot): servicios como
  GoPlus Security o Token Sniffer tienen APIs gratuitas con límites.
