# Realtek Outreach System

Sistema de adquisición de clientes para **Realtek**. Automatiza el seguimiento de inmobiliarias contactadas en EasyBroker: las guarda en Google Sheets y les manda un correo de outreach personalizado esa misma noche.

---

## Cómo funciona en la práctica

```
TÚ (durante el día)                    SISTEMA (automático a las 7 PM)
────────────────────                   ──────────────────────────────
Entras a EasyBroker                    GitHub Actions se activa
Buscas propiedades de otras            Llama la API de EasyBroker y
inmobiliarias y les envías             jala los contactos del día
"Solicitar información" →
EasyBroker crea el contacto            Los guarda en Google Sheets

                                       Manda un email personalizado
                                       a cada uno (1 cada 2-3 min)
                                       alternando rodrigo@ e info@

                                       Si alguien abre o rebota el
                                       email → Sheets se actualiza
                                       automáticamente via webhook
```

---

## Scripts del proyecto

### `main.py` — Orquestador principal
Es el script que conecta todo. Cuando corre, hace en orden:
1. Llama a EasyBroker y trae los contactos del día
2. Los guarda en Google Sheets (sin duplicar)
3. Lee cuáles no han recibido email todavía
4. Les manda el email uno a uno con pausa entre cada envío

```bash
# Correr manualmente una vez
uv run python main.py --run-now

# Limitar a 20 emails en esta corrida
uv run python main.py --run-now --max-emails 20
```

---

### `easybroker_client.py` — Conexión con EasyBroker
Se conecta a la API de EasyBroker y descarga los contactos que se crearon **hoy desde las 00:00 hora México** (los que generaste tú al pedir información en propiedades). Maneja la paginación automáticamente (50 contactos por página).

---

### `sheets_client.py` — Google Sheets
Guarda y lee datos del spreadsheet. Las columnas que maneja:

| Columna | Qué guarda |
|---|---|
| ID, Nombre, Email, Teléfono... | Datos del contacto de EasyBroker |
| Email Enviado | "No" al guardar, "Sí" al enviar |
| Resend ID | ID único del email enviado (para rastrear) |
| Email Abierto | "Sí" cuando el contacto abre el correo |
| Email Entregado | "Sí" cuando llega al servidor destino |
| Rebote | "Sí" si el email no existe o fue rechazado |

La deduplicación es automática: si un contacto ya existe en el sheet (mismo ID de EasyBroker), no se agrega de nuevo aunque el script corra varias noches.

---

### `email_client.py` — Envío de correos via Resend
Envía los correos uno a uno, **no en batch masivo**. Entre cada email espera entre 2 y 3 minutos de forma aleatoria. Esto es intencional: evita que Resend bloquee la cuenta por envíos demasiado rápidos.

Rota entre dos remitentes en orden:
```
Email 1 → rodrigo@realtekmx.com
Email 2 → info@realtekmx.com
Email 3 → rodrigo@realtekmx.com
...
```

El subject y cuerpo del correo se personalizan con el nombre de la agencia (`Empresa` del contacto).

---

### `webhook_server.py` — Servidor de notificaciones
Cuando alguien abre un correo o rebota, Resend manda una notificación (webhook) a este servidor. El servidor actualiza automáticamente la fila correspondiente en Google Sheets.

**Eventos que maneja:**
- `email.opened` → columna "Email Abierto = Sí"
- `email.bounced` → columna "Rebote = Sí"
- `email.delivered` → columna "Email Entregado = Sí"

```bash
# Correr el servidor de webhooks de forma independiente
uv run python webhook_server.py
```

> Por ahora, mientras no hay servidor dedicado, los webhooks se manejan desde n8n (que ya estaba configurado). Cuando haya un servidor (Railway, Render, etc.) este script se deploya ahí.

---

### `browser_outreach.py` — Automatización del outreach en EasyBroker

**Qué hace:** Abre el navegador, entra a EasyBroker y automáticamente hace click en "Solicitar información" en propiedades de otras agencias, llenando el formulario con un mensaje. Esto crea el contacto en EasyBroker que luego el pipeline de la noche procesa.

**Qué es Playwright:** Es una librería de Python que controla un navegador real (Firefox, Chrome, etc.) desde código, igual que si tú hicieras los clicks. Lo que hace diferente a un bot detectado es que usa tu perfil real del navegador, con tus cookies y sesión activa.

**Qué es Zen Browser:** Es el navegador que usas normalmente (basado en Firefox). Playwright lo abre con tu perfil ya guardado, así EasyBroker ve una sesión real tuya, no un browser limpio de bot.

**Por qué no es detectado (o lo es menos):**
- El browser se abre visible en pantalla, no en modo invisible
- Usa tu sesión real de EasyBroker (con historial, cookies, etc.)
- Escribe los mensajes letra por letra con velocidad variable, como un humano
- Espera tiempos aleatorios entre cada acción

```bash
# Instalar Firefox para Playwright (primera vez)
uv run playwright install firefox

# Prueba sin enviar nada (solo navega)
uv run python browser_outreach.py --dry-run --max 5

# Correr en producción con 100 propiedades
uv run python browser_outreach.py --max 100
```

> **Estado actual:** Los selectores del formulario de EasyBroker (el botón "Solicitar información" y el textarea del modal) están pendientes de calibrar. Se necesita inspeccionar el elemento en DevTools para obtener el selector exacto.

---

## GitHub Actions — Automatización nocturna

El archivo `.github/workflows/outreach.yml` programa el pipeline para correr automáticamente **todos los días a las 7 PM hora México** (sin que tengas que hacer nada).

**Lo que hace cada noche:**
1. Levanta un servidor Ubuntu en GitHub
2. Instala Python y las dependencias
3. Corre `main.py --run-now --max-emails 100`
4. El servidor se apaga solo cuando termina

**Trigger manual:** En GitHub → Actions → "Realtek Outreach Pipeline" → "Run workflow" puedes lanzarlo a mano cuando quieras, y puedes cambiar el límite de emails para esa corrida.

---

## Configuración inicial (una sola vez)

### 1. Instalar dependencias
```bash
uv sync
uv run playwright install firefox
```

### 2. Crear el archivo `.env`
Copia el ejemplo y llena los valores:
```bash
cp .env.example .env
```

### 3. Variables requeridas en `.env`

| Variable | Dónde conseguirla |
|---|---|
| `EASYBROKER_API_KEY` | EasyBroker → Configuración → API |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Cloud → IAM → Service Accounts → JSON |
| `GOOGLE_SPREADSHEET_ID` | URL del sheet: `.../d/ESTE_ID/edit` |
| `RESEND_API_KEY` | app.resend.com → API Keys |
| `RESEND_FROM_EMAILS` | `rodrigo@realtekmx.com,info@realtekmx.com` |
| `ZEN_PROFILE_PATH` | Ruta al perfil de Zen Browser (se detecta automático en Linux) |

### 4. Secrets en GitHub
Para que GitHub Actions funcione, agrega los mismos valores en:
**Repositorio → Settings → Secrets and variables → Actions**

El `GOOGLE_SERVICE_ACCOUNT_JSON` se pega como el **contenido completo del JSON** (no la ruta al archivo).

---

## Estructura de archivos

```
outreach-system/
│
├── main.py                  # Punto de entrada — orquesta todo el pipeline
├── easybroker_client.py     # API de EasyBroker: trae contactos del día
├── sheets_client.py         # Google Sheets: guarda, lee y actualiza filas
├── email_client.py          # Resend: envía emails con delay y rota remitentes
├── webhook_server.py        # FastAPI: recibe eventos de Resend y actualiza Sheets
├── browser_outreach.py      # Playwright: automatiza "Solicitar info" en EasyBroker
│
├── .github/
│   └── workflows/
│       └── outreach.yml     # Cron job de GitHub Actions (7 PM México diario)
│
├── outreach_log.json        # Log local de propiedades contactadas (browser_outreach)
├── .env                     # Variables de entorno (NO subir a git)
└── pyproject.toml           # Dependencias del proyecto
```

---

## Flujo completo día a día

```
MAÑANA/TARDE
  └── (Opcional) browser_outreach.py  →  hace click en "Solicitar info"
                                          en propiedades de EasyBroker
                                          → EasyBroker crea los contactos

7:00 PM — GitHub Actions arranca automáticamente
  └── easybroker_client.py   →  GET /v1/contacts?search[updated_after]=hoy 00:00
  └── sheets_client.py       →  guarda contactos nuevos en Sheets
  └── email_client.py        →  envía emails (1 cada 2-3 min, rota rodrigo@/info@)
                                lleva ~3-5 horas para 100 emails

CUANDO ALGUIEN ABRE / REBOTA EL EMAIL
  └── Resend → webhook → webhook_server.py  →  actualiza columna en Sheets
      (por ahora este paso se maneja desde n8n)
```
