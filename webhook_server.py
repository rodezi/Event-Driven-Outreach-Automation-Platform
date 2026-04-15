"""
Servidor de webhooks para eventos de Resend — FastAPI.

Endpoints:
  POST /webhook/resend  → email.opened / email.delivered / email.bounced
  GET  /health          → healthcheck
  GET  /dashboard       → dashboard de outreach
  GET  /api/contacts    → datos JSON del sheet

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
from fastapi.responses import HTMLResponse, JSONResponse

from sheets_client import update_email_event, _open_worksheet

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


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Realtek Outreach</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f6fa; color: #1a1a2e; font-size: 14px; }

  /* NAV */
  .nav { background: #fff; border-bottom: 1px solid #e8eaed; padding: 0 28px;
         display: flex; align-items: center; height: 56px; gap: 12px; }
  .nav-logo { font-weight: 700; font-size: 16px; color: #1a1a2e; }
  .nav-dot  { width: 8px; height: 8px; background: #4f46e5; border-radius: 50%; }
  .nav-sub  { color: #6b7280; font-size: 13px; margin-left: 4px; }

  /* MAIN */
  .main { max-width: 1200px; margin: 0 auto; padding: 28px 24px; }

  /* STATS */
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
           gap: 16px; margin-bottom: 28px; }
  .card  { background: #fff; border-radius: 12px; border: 1px solid #e8eaed;
           padding: 20px 22px; }
  .card-label { font-size: 12px; font-weight: 500; color: #6b7280;
                text-transform: uppercase; letter-spacing: .5px; margin-bottom: 10px; }
  .card-value { font-size: 32px; font-weight: 700; color: #1a1a2e; line-height: 1; }
  .card-pct   { font-size: 13px; color: #6b7280; margin-top: 5px; }
  .card-pct span { font-weight: 600; }
  .pct-green { color: #10b981; }
  .pct-red   { color: #ef4444; }
  .pct-blue  { color: #4f46e5; }

  /* TABLE SECTION */
  .section-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; color: #374151; }
  .table-wrap { background: #fff; border-radius: 12px; border: 1px solid #e8eaed; overflow: hidden; }
  table { width: 100%; border-collapse: collapse; }
  thead th { background: #f9fafb; padding: 11px 16px; text-align: left;
             font-size: 11px; font-weight: 600; text-transform: uppercase;
             letter-spacing: .5px; color: #6b7280; border-bottom: 1px solid #e8eaed; }
  tbody tr { border-bottom: 1px solid #f1f3f5; transition: background .1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: #fafbff; }
  tbody td { padding: 11px 16px; color: #374151; }
  .td-name   { font-weight: 500; color: #1a1a2e; }
  .td-email  { color: #6b7280; font-size: 13px; }
  .td-company{ color: #6b7280; font-size: 13px; }

  /* BADGES */
  .badge { display: inline-flex; align-items: center; gap: 5px; border-radius: 20px;
           padding: 3px 10px; font-size: 12px; font-weight: 500; white-space: nowrap; }
  .badge-yes { background: #ecfdf5; color: #059669; }
  .badge-no  { background: #f3f4f6; color: #9ca3af; }
  .badge-sent{ background: #eff6ff; color: #2563eb; }
  .badge-bounce{ background: #fef2f2; color: #dc2626; }

  .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .dot-green  { background: #10b981; }
  .dot-gray   { background: #d1d5db; }
  .dot-blue   { background: #3b82f6; }
  .dot-red    { background: #ef4444; }

  /* LOADING / EMPTY */
  .loading { text-align: center; padding: 40px; color: #9ca3af; font-size: 14px; }
  .refresh-note { text-align: right; font-size: 11px; color: #9ca3af; margin-top: 10px; }

  /* SEARCH */
  .toolbar { display: flex; align-items: center; justify-content: space-between;
             margin-bottom: 14px; }
  .search  { border: 1px solid #e8eaed; border-radius: 8px; padding: 8px 13px;
             font-size: 13px; outline: none; width: 220px; background: #fff; }
  .search:focus { border-color: #4f46e5; }
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-dot"></div>
  <span class="nav-logo">Realtek Outreach</span>
  <span class="nav-sub">/ Dashboard</span>
</nav>

<main class="main">

  <!-- STATS CARDS -->
  <div class="stats" id="stats">
    <div class="card"><div class="card-label">Enviados</div>
      <div class="card-value" id="s-sent">—</div></div>
    <div class="card"><div class="card-label">Abiertos</div>
      <div class="card-value" id="s-opens">—</div>
      <div class="card-pct"><span class="pct-green" id="s-open-pct">—</span> open rate</div></div>
    <div class="card"><div class="card-label">Entregados</div>
      <div class="card-value" id="s-delivered">—</div>
      <div class="card-pct"><span class="pct-blue" id="s-del-pct">—</span> delivery rate</div></div>
    <div class="card"><div class="card-label">Rebotes</div>
      <div class="card-value" id="s-bounces">—</div>
      <div class="card-pct"><span class="pct-red" id="s-bounce-pct">—</span> bounce rate</div></div>
    <div class="card"><div class="card-label">Pendientes</div>
      <div class="card-value" id="s-pending">—</div></div>
  </div>

  <!-- TABLE -->
  <div class="toolbar">
    <span class="section-title">Contactos</span>
    <input class="search" type="text" id="search" placeholder="Buscar nombre, empresa, email…" oninput="filterTable()">
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Nombre</th>
          <th>Empresa</th>
          <th>Email</th>
          <th>Enviado</th>
          <th>Entregado</th>
          <th>Abierto</th>
          <th>Rebote</th>
          <th>Fecha</th>
        </tr>
      </thead>
      <tbody id="tbody">
        <tr><td colspan="8" class="loading">Cargando datos…</td></tr>
      </tbody>
    </table>
  </div>
  <div class="refresh-note" id="last-update"></div>

</main>

<script>
let allRows = [];

function pct(n, total) {
  if (!total) return '0%';
  return (n / total * 100).toFixed(1) + '%';
}

function badge(val, type) {
  if (type === 'sent') {
    if (val === 'Sí') return '<span class="badge badge-sent"><span class="dot dot-blue"></span>Enviado</span>';
    return '<span class="badge badge-no"><span class="dot dot-gray"></span>Pendiente</span>';
  }
  if (type === 'bounce') {
    if (val === 'Sí') return '<span class="badge badge-bounce"><span class="dot dot-red"></span>Rebote</span>';
    return '<span class="badge badge-no">—</span>';
  }
  if (val === 'Sí') return '<span class="badge badge-yes"><span class="dot dot-green"></span>Sí</span>';
  return '<span class="badge badge-no">—</span>';
}

function renderTable(rows) {
  const tbody = document.getElementById('tbody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading">Sin resultados.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="td-name">${r.nombre || '—'}</td>
      <td class="td-company">${r.empresa || '—'}</td>
      <td class="td-email">${r.email || '—'}</td>
      <td>${badge(r.email_enviado, 'sent')}</td>
      <td>${badge(r.email_entregado, 'default')}</td>
      <td>${badge(r.email_abierto, 'default')}</td>
      <td>${badge(r.rebote, 'bounce')}</td>
      <td style="color:#9ca3af;font-size:12px">${r.creado_en ? r.creado_en.slice(0,10) : '—'}</td>
    </tr>
  `).join('');
}

function filterTable() {
  const q = document.getElementById('search').value.toLowerCase();
  if (!q) { renderTable(allRows); return; }
  renderTable(allRows.filter(r =>
    (r.nombre||'').toLowerCase().includes(q) ||
    (r.empresa||'').toLowerCase().includes(q) ||
    (r.email||'').toLowerCase().includes(q)
  ));
}

async function load() {
  try {
    const res = await fetch('/api/contacts');
    const data = await res.json();
    allRows = data.contacts;

    const sent      = allRows.filter(r => r.email_enviado === 'Sí').length;
    const opens     = allRows.filter(r => r.email_abierto === 'Sí').length;
    const delivered = allRows.filter(r => r.email_entregado === 'Sí').length;
    const bounces   = allRows.filter(r => r.rebote === 'Sí').length;
    const pending   = allRows.filter(r => r.email_enviado === 'No' && r.email).length;

    document.getElementById('s-sent').textContent      = sent;
    document.getElementById('s-opens').textContent     = opens;
    document.getElementById('s-delivered').textContent = delivered;
    document.getElementById('s-bounces').textContent   = bounces;
    document.getElementById('s-pending').textContent   = pending;
    document.getElementById('s-open-pct').textContent  = pct(opens, sent);
    document.getElementById('s-del-pct').textContent   = pct(delivered, sent);
    document.getElementById('s-bounce-pct').textContent= pct(bounces, sent);

    renderTable(allRows);
    document.getElementById('last-update').textContent =
      'Actualizado: ' + new Date().toLocaleTimeString('es-MX');
  } catch(e) {
    document.getElementById('tbody').innerHTML =
      '<tr><td colspan="8" class="loading">Error cargando datos.</td></tr>';
  }
}

load();
setInterval(load, 60000); // refresca cada 60 segundos
</script>
</body>
</html>"""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/api/contacts")
async def api_contacts() -> JSONResponse:
    """Retorna todos los contactos del sheet como JSON para el dashboard."""
    try:
        ws = _open_worksheet()
        all_values = ws.get_all_values()
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    if len(all_values) <= 1:
        return JSONResponse({"contacts": []})

    headers = all_values[0]

    def col(row: list, name: str) -> str:
        try:
            return row[headers.index(name)]
        except (ValueError, IndexError):
            return ""

    contacts = []
    for row in all_values[1:]:
        contacts.append({
            "nombre":          col(row, "Nombre"),
            "empresa":         col(row, "Empresa"),
            "email":           col(row, "Email"),
            "email_enviado":   col(row, "Email Enviado"),
            "email_abierto":   col(row, "Email Abierto"),
            "email_entregado": col(row, "Email Entregado"),
            "rebote":          col(row, "Rebote"),
            "creado_en":       col(row, "Creado en"),
        })

    return JSONResponse({"contacts": contacts})


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.getenv("WEBHOOK_PORT", "8080"))
    print(f"[webhook] Iniciando en puerto {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
