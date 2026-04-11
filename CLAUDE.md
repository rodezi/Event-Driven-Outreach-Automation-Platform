# Realtek Outreach System

Sistema de adquisición de clientes de Realtek dirigido a inmobiliarias.

## Flujo operativo

### Durante el día (manual — Rodrigo)
Rodrigo hace outreach manual desde la plataforma de EasyBroker: contacta inmobiliarias preguntando por propiedades. Ese intercambio crea automáticamente el contacto en EasyBroker con nombre, email, teléfono y empresa.

### En la noche (automático — GitHub Actions, 9 PM hora México)
El pipeline corre y:
1. Jala todos los contactos nuevos de EasyBroker via API (`GET /v1/contacts`)
2. Guarda los que no existan aún en Google Sheets (deduplicación por ID)
3. Envía un email de seguimiento a cada contacto pendiente, uno a uno con 2-3 min de delay entre cada uno
4. Rota entre `rodrigo@realtekmx.com` e `info@realtekmx.com` para distribuir el volumen
5. Registra el Resend ID por fila para rastrear aperturas y rebotes via webhook

## Límites y configuración
- Emails por corrida: configurable con `--max-emails` (default 100 en el workflow)
- Delay entre emails: 2-3 minutos aleatorio (respeta límites de Resend)
- Remitentes: `RESEND_FROM_EMAILS` en GitHub Secrets (separados por coma)
- La deduplicación evita mandar el mismo email dos veces aunque el pipeline corra varias noches
- Resend Pro recomendado ($20/mes) — el free tier es exactamente 3,000/mes y puede fallar al límite
- Repo público recomendado en GitHub para tener minutos de Actions ilimitados (los Secrets siguen privados)

## Webhooks (eventos de email)
- `email.opened` → columna "Email Abierto = Sí" en Sheets
- `email.bounced` → columna "Rebote = Sí" en Sheets
- `email.delivered` → columna "Email Entregado = Sí" en Sheets
- Mientras no haya servidor: manejar desde n8n (flujo ya existente)
- Futuro: `python webhook_server.py` deployado en Railway/Render
