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
Conecta todo el pipeline. Cuando corre hace en orden:
1. Llama a EasyBroker y trae los contactos del día
2. Los guarda en Google Sheets (sin duplicar)
3. Lee cuáles no han recibido email todavía
4. Les manda el email uno a uno con pausa entre cada envío

```bash
uv run python main.py --run-now
uv run python main.py --run-now --max-emails 20
```

---

### `easybroker_client.py` — Conexión con EasyBroker
Descarga los contactos creados **hoy desde las 00:00 hora México**. Maneja paginación automáticamente (50 contactos por página).

---

### `sheets_client.py` — Google Sheets
Guarda y lee datos del spreadsheet:

| Columna | Qué guarda |
|---|---|
| ID, Nombre, Email, Teléfono... | Datos del contacto de EasyBroker |
| Email Enviado | "No" al guardar, "Sí" al enviar |
| Resend ID | ID único del email (para rastrear webhooks) |
| Email Abierto | "Sí" cuando el contacto abre el correo |
| Email Entregado | "Sí" cuando llega al servidor destino |
| Rebote | "Sí" si el email no existe o fue rechazado |

La deduplicación es automática por ID de EasyBroker.

---

### `email_client.py` — Envío de correos via Resend
Envía uno a uno con **2-3 minutos de pausa aleatoria** entre cada email. Rota remitentes:
```
Email 1 → rodrigo@realtekmx.com
Email 2 → info@realtekmx.com
Email 3 → rodrigo@realtekmx.com
...
```

---

### `webhook_server.py` — Servidor de notificaciones (Railway)
Cuando alguien abre un correo o rebota, Resend notifica a este servidor y actualiza Google Sheets automáticamente.

**Eventos:**
- `email.opened` → "Email Abierto = Sí"
- `email.delivered` → "Email Entregado = Sí"
- `email.bounced` → "Rebote = Sí"

```bash
uv run python webhook_server.py
```

---

## GitHub Actions — Automatización nocturna

El pipeline corre automáticamente **todos los días a las 7 PM hora México**.

**Trigger manual:** GitHub → Actions → "Realtek Outreach Pipeline" → "Run workflow"

---

## Configuración inicial

### 1. Instalar dependencias
```bash
uv sync
```

### 2. Variables de entorno (`.env`)

| Variable | Dónde conseguirla |
|---|---|
| `EASYBROKER_API_KEY` | EasyBroker → Configuración → API |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Cloud → IAM → Service Accounts → JSON |
| `GOOGLE_SPREADSHEET_ID` | URL del sheet: `.../d/ESTE_ID/edit` |
| `RESEND_API_KEY` | app.resend.com → API Keys |
| `RESEND_FROM_EMAILS` | `rodrigo@realtekmx.com,info@realtekmx.com` |
| `RESEND_WEBHOOK_SECRET` | Resend → Webhooks → Signing Secret |

### 3. Secrets en GitHub
Agrega los mismos valores en:
**Repositorio → Settings → Secrets and variables → Actions**

> `GOOGLE_SERVICE_ACCOUNT_JSON` va como el **contenido completo del JSON**, no la ruta al archivo.

### 4. Dar acceso al Sheet a la Service Account
Compartir el Google Sheet con el email de la service account (`...@...iam.gserviceaccount.com`) como **Editor**.

---

## Estructura de archivos

```
outreach-system/
├── main.py                  # Orquesta todo el pipeline
├── easybroker_client.py     # API de EasyBroker: trae contactos del día
├── sheets_client.py         # Google Sheets: guarda, lee y actualiza filas
├── email_client.py          # Resend: envía emails con delay y rota remitentes
├── webhook_server.py        # FastAPI: recibe eventos de Resend → actualiza Sheets
├── Procfile                 # Config de deploy para Railway
├── .github/
│   └── workflows/
│       └── outreach.yml     # Cron job GitHub Actions (7 PM México diario)
├── .env                     # Variables de entorno (NO subir a git)
└── pyproject.toml           # Dependencias del proyecto
```
