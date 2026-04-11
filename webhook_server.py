"""
Servidor de webhooks para eventos de Resend — FastAPI.

Endpoints:
  POST /webhook/resend  → email.opened / email.delivered / email.bounced
  GET  /health          → healthcheck

Verificación de firma Svix/Resend:
  Requiere RESEND_WEBHOOK_SECRET en .env o variables de entorno del deploy.
  Incluye protección contra replay attacks (ventana de 5 minutos).
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, Response

from sheets_client import update_email_event

app = FastAPI(title="Realtek Webhook Server")

SUPPORTED_EVENTS = {"email.opened", "email.delivered", "email.bounced"}
SVIX_TIMESTAMP_TOLERANCE = 300  # 5 minutos

_sheet_lock = threading.Lock()


# ── Verificación de firma ──────────────────────────────────────────────────────

def _verify_svix_signature(
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    """
    Valida la firma HMAC-SHA256 que Resend adjunta via Svix.
    Mensaje firmado: "{svix_id}.{svix_timestamp}.{body}"
    Rechaza si el timestamp tiene más de 5 minutos.
    """
    secret = os.getenv("RESEND_WEBHOOK_SECRET", "")
    if not secret:
        print("[webhook] ADVERTENCIA: RESEND_WEBHOOK_SECRET no configurado — verificación omitida.")
        return True

    # Protección contra replay attacks: validar que el timestamp sea reciente
    try:
        ts = int(svix_timestamp)
        if abs(time.time() - ts) > SVIX_TIMESTAMP_TOLERANCE:
            print(f"[webhook] Timestamp fuera de ventana ({svix_timestamp}) — request rechazado")
            return False
    except ValueError:
        print(f"[webhook] Timestamp inválido: {svix_timestamp}")
        return False

    # El secret de Svix viene con prefijo "whsec_" en base64
    raw_secret = secret.removeprefix("whsec_")
    try:
        secret_bytes = base64.b64decode(raw_secret)
    except Exception:
        secret_bytes = raw_secret.encode()

    try:
        body_str = payload.decode("utf-8")
    except UnicodeDecodeError:
        print("[webhook] Body con bytes no-UTF8 — request rechazado")
        return False

    to_sign = f"{svix_id}.{svix_timestamp}.{body_str}".encode()
    computed = base64.b64encode(
        hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    ).decode()

    # svix_signature puede contener múltiples firmas: "v1,abc v1,xyz"
    candidates = [s.split(",", 1)[-1] for s in svix_signature.split()]
    return any(hmac.compare_digest(computed, c) for c in candidates)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook/resend")
async def resend_webhook(
    request: Request,
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
) -> Response:
    raw_body = await request.body()

    secret_configured = bool(os.getenv("RESEND_WEBHOOK_SECRET", "").strip())

    if secret_configured:
        # Si el secret está configurado, los headers Svix son obligatorios
        if not (svix_id and svix_timestamp and svix_signature):
            print("[webhook] Secret configurado pero faltan headers Svix — request rechazado")
            raise HTTPException(status_code=401, detail="Missing Svix headers")
        if not _verify_svix_signature(raw_body, svix_id, svix_timestamp, svix_signature):
            print("[webhook] Firma inválida — request rechazado")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type: str = payload.get("type", "")
    data: dict = payload.get("data", {})
    resend_id: str = data.get("email_id", "")
    to_list = data.get("to")
    to_email: str = str(to_list[0]) if to_list else ""

    print(f"[webhook] {event_type} | Resend ID: {resend_id} | to: {to_email}")

    if event_type not in SUPPORTED_EVENTS:
        return Response(content="OK", status_code=200)

    if not resend_id:
        print("[webhook] Payload sin email_id — ignorando")
        return Response(content="OK", status_code=200)

    with _sheet_lock:
        try:
            found = update_email_event(resend_id, event_type)
            if not found:
                print(f"[webhook] Resend ID {resend_id} no encontrado en el sheet")
        except Exception as exc:
            # Retornar 200 para que Resend no reintente indefinidamente
            print(f"[webhook] Error actualizando sheet: {exc}")

    return Response(content="OK", status_code=200)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.getenv("WEBHOOK_PORT", "8080"))
    print(f"[webhook] Iniciando en puerto {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
