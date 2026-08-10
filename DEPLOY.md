# Cómo dejar el detector corriendo sin tener el PC encendido

Hay dos formas. Recomiendo empezar por la **Opción A (GitHub Actions)** porque
es gratis, no requiere pagar un servidor, y el setup toma ~15 minutos.

---

## Opción A: GitHub Actions (gratis, recomendada para empezar)

GitHub ejecuta `run_once.py` cada 15 minutos en sus propios servidores. Tu PC
no necesita estar prendido para nada.

**Limitación a tener en cuenta:** GitHub no garantiza que el cron corra
exactamente cada 15 min al segundo (puede haber retrasos de minutos en horas
de alta carga), y si el repositorio queda sin actividad por 60 días, GitHub
desactiva automáticamente los workflows programados (hay que reactivarlo con
un commit o manualmente).

### Paso 1: Crear el bot de Telegram (para recibir las notificaciones)

1. Abre Telegram y busca **@BotFather**.
2. Envía `/newbot`, ponle un nombre y un username (debe terminar en `bot`).
3. BotFather te da un **token** tipo `123456789:ABCdefGHIjklMNOpqrsTUVwxyz` — guárdalo.
4. Busca **@userinfobot** en Telegram, envíale cualquier mensaje, y te devuelve
   tu **chat_id** (un número). Guárdalo también.
5. Importante: envíale **un mensaje cualquiera a tu bot recién creado** (búscalo
   por su username) — si no le escribes primero, el bot no puede enviarte
   mensajes a ti.

### Paso 2: Crear el repositorio en GitHub

1. Ve a [github.com/new](https://github.com/new), crea un repo (puede ser
   privado — GitHub Actions funciona igual en repos privados con minutos
   gratis limitados, más que suficiente para este uso).
2. Sube todos los archivos de este proyecto al repo. Desde tu PC, en la
   carpeta del proyecto:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### Paso 3: Configurar los secrets

1. En tu repo en GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
2. Crea dos secrets:
   - `TELEGRAM_BOT_TOKEN` → el token del Paso 1.
   - `TELEGRAM_CHAT_ID` → tu chat_id del Paso 1.

### Paso 4: Activar el workflow

El archivo `.github/workflows/scan.yml` ya está incluido en el proyecto. Al
subirlo, GitHub lo detecta automáticamente.

1. Ve a la pestaña **Actions** de tu repo.
2. Deberías ver el workflow "Crypto Scanner". Si te pide habilitarlo, hazlo.
3. Para probarlo sin esperar 15 min: click en el workflow → **Run workflow**
   (botón manual, gracias a `workflow_dispatch` en el yml).
4. Revisa los logs de la ejecución — ahí verás cuántos candidatos se
   evaluaron y si hubo alertas, aunque no cumplan el umbral de notificación.

Si todo está bien configurado, en unos minutos deberías recibir un mensaje de
tu bot de Telegram (si hay algún token que cumpla el score mínimo) o ver el
log en Actions confirmando que corrió sin errores.

### Cómo pausarlo o detenerlo

- **Pausar temporalmente**: Settings → Actions → General → Disable actions,
  o simplemente comenta la sección `schedule:` en `scan.yml`.
- **Detener del todo**: borra el archivo `.github/workflows/scan.yml` o el repo.

---

## Opción B: VPS propio (más control, sin límites de GitHub, cuesta dinero)

Si más adelante quieres algo más confiable (sin depender de que GitHub no
desactive el cron), puedes rentar un VPS barato (Hetzner, DigitalOcean,
Vultr — desde ~$4-6 USD/mes) y correr `auto_scan.py` como servicio.

### Paso 1: Conectarte al VPS y preparar el entorno

```bash
ssh tu_usuario@ip_del_vps
sudo apt update && sudo apt install -y python3 python3-venv git
git clone https://github.com/TU_USUARIO/TU_REPO.git crypto-detector
cd crypto-detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Paso 2: Probar manualmente antes de dejarlo en automático

```bash
python run_once.py
```

Confirma que corre sin errores y (si configuraste Telegram) que llega la
notificación de prueba.

### Paso 3: Configurar como servicio systemd (para que sobreviva reinicios)

1. Copia `systemd/crypto-detector.service` a `/etc/systemd/system/`:

```bash
sudo cp systemd/crypto-detector.service /etc/systemd/system/
sudo nano /etc/systemd/system/crypto-detector.service
```

2. Edita las líneas `WorkingDirectory`, `ExecStart` (rutas reales del VPS) y
   las variables `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

3. Activa el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-detector
sudo systemctl start crypto-detector
```

4. Verificar que está corriendo:

```bash
sudo systemctl status crypto-detector
journalctl -u crypto-detector -f   # ver logs en vivo
```

Con esto, el detector corre 24/7 en el VPS, se reinicia solo si falla
(`Restart=always`), y sobrevive reinicios del servidor.

---

## Recomendación

Empieza con **GitHub Actions** — es gratis y suficiente para validar si el
detector te sirve. Si en unas semanas ves que el approach funciona y quieres
más confiabilidad (o vas a agregar la parte de Fase 2 con ML, que puede
necesitar más recursos), migra a un VPS.
