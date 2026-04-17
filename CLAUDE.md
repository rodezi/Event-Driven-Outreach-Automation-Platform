# Realtek Outreach System

Sistema de adquisición de clientes de Realtek dirigido a inmobiliarias en México.

## Arquitectura general

```
Railway (madrugada)          Google Sheets           GitHub Actions (7 AM)
─────────────────────        ─────────────────       ──────────────────────
scraper.py                →  master dataset      →   main.py
  Google Maps por ciudad       (todos los             envía 100 emails/día
  colonia por colonia           contactos)            con delay 2-3 min

email_enricher.py         →  llena col. Email
  visita sitio web de
  cada contacto sin email
```

## Flujo operativo

### 2:00 AM — Railway: scraper.py
Scrapea Google Maps ciudad por ciudad, zona por zona:
- Extrae: nombre, teléfono, sitio web, rating, dirección
- Guarda en Google Sheets (deduplicación por teléfono)
- Columna `Fuente = "Google Maps"`, `Web = url del sitio`

### ~3:30 AM — Railway: email_enricher.py
Para cada fila donde `Email` está vacío y `Web` tiene URL:
- Visita la página principal + /contacto + /nosotros + /about
- Extrae el primer email válido del HTML
- Actualiza columna `Email` en el sheet

### 7:00 AM — GitHub Actions: main.py
- Lee filas donde `Email Enviado = "No"` y `Email != ""`
- Envía hasta 100 emails por corrida con delay aleatorio de 2-3 min
- Rota entre remitentes configurados en `RESEND_FROM_EMAILS`
- Registra Resend ID para tracking de aperturas/rebotes

## Ciudades y estrategia de scraping

Ciudades en `cities.py`, organizadas por zonas/colonias para maximizar cobertura
(Google Maps limita ~120-200 resultados por query).

**Orden de ejecución planeado:**
1. CDMX — 79 zonas, estimado 2,700-5,500 contactos
2. QUERETARO — 10 zonas, estimado 200-400 contactos
3. GUADALAJARA, MONTERREY, CANCUN, LOS_CABOS, TOLUCA, MORELIA, PUEBLA, MERIDA

Para cambiar de ciudad: actualizar variable `SCRAPER_CITY` en Railway dashboard.

## Archivos clave

| Archivo | Rol |
|---|---|
| `scraper.py` | Google Maps → Sheets. Arg: `--city CDMX` |
| `email_enricher.py` | Visita webs → llena emails en Sheets |
| `main.py` | Lee Sheets → envía emails vía Resend |
| `cities.py` | Config de queries por ciudad/zona |
| `sheets_client.py` | Toda la lógica de lectura/escritura al Sheet |
| `email_client.py` | Lógica de envío y rotación de remitentes |
| `webhook_server.py` | Recibe eventos de Resend (opened/bounced/delivered) |

## Google Sheets — columnas

| Columna | Descripción |
|---|---|
| ID | `scraper-{telefono}` para leads del scraper |
| Nombre | Nombre del negocio |
| Email | Email encontrado por el enricher |
| Teléfono | Teléfono principal |
| Empresa | Mismo que Nombre para leads del scraper |
| Fuente | `"Google Maps"` |
| Web | URL del sitio web |
| Email Enviado | `"No"` / `"Sí"` |
| Resend ID | Para rastrear webhooks |
| Email Abierto / Entregado / Rebote | Actualizados por webhook |

## Variables de entorno

### Railway (scraper + enricher)
```
SCRAPER_CITY=CDMX
GOOGLE_SPREADSHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
```

### GitHub Secrets (email pipeline)
```
GOOGLE_SPREADSHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON
RESEND_API_KEY
RESEND_FROM_EMAILS     # ej: rodrigo@realtekmx.com,info@realtekmx.com
```

## Límites y configuración
- Emails por corrida: 100 (configurable con `--max-emails`)
- Delay entre emails: 2-3 minutos aleatorio
- Resend Pro recomendado ($20/mes) — free tier es 3,000/mes exacto
- Repo público en GitHub para minutos de Actions ilimitados (Secrets siguen privados)

## Webhooks (eventos de email)
- `email.opened` → `Email Abierto = "Sí"`
- `email.bounced` → `Rebote = "Sí"`
- `email.delivered` → `Email Entregado = "Sí"`
- Actualmente manejado desde n8n
- Futuro: `python webhook_server.py` en Railway/Render

## Comandos útiles

```bash
# Scraper local
python scraper.py --list-cities
python scraper.py --city CDMX
python scraper.py --city CDMX --headless false   # ver el browser
python scraper.py --city CDMX --csv backup.csv   # + guardar CSV

# Enricher local
python email_enricher.py --dry-run               # simula sin escribir
python email_enricher.py --limit 50

# Pipeline de emails local
python main.py --max-emails 10

# EasyBroker (rama: easybroker-backup)
# Preservado por si se reactiva la integración
```

## Deploy

### Railway (scraper + enricher)
- Builder: Dockerfile
- Variables: `SCRAPER_CITY`, `GOOGLE_SPREADSHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`
- Cron: `0 8 * * *` (2 AM CST)
- Comando: `python scraper.py --city ${SCRAPER_CITY} && python email_enricher.py --limit 500`

### GitHub Actions
- Cron: `0 13 * * *` (7 AM CST)
- Workflow: `.github/workflows/outreach.yml`
