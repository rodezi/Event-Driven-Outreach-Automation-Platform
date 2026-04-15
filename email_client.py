"""
Envío de emails via Resend con:
  - Rotación de remitentes (rodrigo@realtekmx.com → info@realtekmx.com → ...)
  - Delay aleatorio de 2-3 min entre cada envío (configurable)
  - Callback post-envío para persistir el Resend ID inmediatamente
"""

import os
import random
import time
from itertools import cycle
from typing import Callable

import resend

SEND_DELAY_MIN = int(os.getenv("SEND_DELAY_MIN_SECONDS", "120"))  # 2 min
SEND_DELAY_MAX = int(os.getenv("SEND_DELAY_MAX_SECONDS", "180"))  # 3 min


def _get_senders() -> list[str]:
    """
    Lee RESEND_FROM_EMAILS (lista separada por comas).
    Fallback a RESEND_FROM_EMAIL si solo hay uno.
    Ejemplo .env:
      RESEND_FROM_EMAILS=rodrigo@realtekmx.com,info@realtekmx.com
    """
    multi = os.getenv("RESEND_FROM_EMAILS", "").strip()
    if multi:
        return [s.strip() for s in multi.split(",") if s.strip()]

    single = os.getenv("RESEND_FROM_EMAIL", "").strip()
    if single:
        return [single]

    raise ValueError(
        "Define RESEND_FROM_EMAILS (ej: rodrigo@realtekmx.com,info@realtekmx.com) en .env"
    )


def _build_subject(row: dict) -> str:
    agencia = row.get("Empresa") or row.get("Nombre") or "su agencia"
    subject_tpl = os.getenv("RESEND_EMAIL_SUBJECT", "").strip() or \
        "algo que encontré para {agencia}"
    return subject_tpl.replace("{agencia}", agencia)


def _build_email_body(row: dict, from_email: str) -> str:
    nombre = row.get("Nombre") or ""
    agencia = row.get("Empresa") or nombre or "su agencia"
    saludo = f"Hola{', ' + nombre.split()[0] if nombre else ''},"

    return f"""\
<html>
<body style="font-family: Georgia, serif; color: #1a1a1a; max-width: 560px; margin: auto; line-height: 1.75; font-size: 15px;">

  <p>{saludo}</p>

  <p>Nos cruzamos en EasyBroker hace unos días y me quedé pensando en algo
  que vale la pena compartirle.</p>

  <p>Revisé cómo responden a prospectos inmobiliarias similares a
  <strong>{agencia}</strong> en su zona, y encontré algo concreto:
  la mayoría pierde entre el 40 y 60% de sus leads simplemente por tiempo
  de respuesta — no por precio, ni por inventario.</p>

  <p>Con las agencias con las que trabajamos, ese tiempo bajó de un promedio
  de 3 horas a <strong>menos de 90 segundos</strong>. En los primeros 30 días,
  el 78% reportó más visitas agendadas sin contratar a nadie nuevo.</p>

  <p>Llevamos 3 años trabajando exclusivamente con inmobiliarias en México.
  No somos una agencia de marketing genérica — conocemos EasyBroker,
  los ciclos de compra locales y los retos específicos del sector.</p>

  <p>Antes de pedirle cualquier cosa: ¿le mando un video de 90 segundos
  donde le muestro exactamente cómo funcionaría para
  <strong>{agencia}</strong>?</p>

  <p>Solo responda <strong>"sí"</strong> y se lo envío hoy.</p>

  <p>
    Rodrigo<br>
    Realtek &mdash; <a href="tel:4427920802" style="color:#1a1a1a;">442 792 0802</a>
  </p>

  <p style="color: #777; font-size: 13px;">
    PD: Por política interna trabajo con máximo dos agencias por zona
    para no generar conflicto de interés. Si ya hay una en su área,
    se lo digo de entrada.
  </p>

</body>
</html>"""


def send_single_email(row: dict, from_email: str) -> str | None:
    """
    Envía un email desde from_email al contacto de la fila.
    Retorna el Resend ID si fue exitoso, None si falló.
    """
    resend.api_key = os.getenv("RESEND_API_KEY")
    if not resend.api_key:
        raise ValueError("RESEND_API_KEY no está definida")

    to_email = row.get("Email", "").strip()
    if not to_email:
        return None

    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "reply_to": os.getenv("RESEND_REPLY_TO", "rodrigo@realtekmx.com"),
            "subject": _build_subject(row),
            "html": _build_email_body(row, from_email),
        })
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        return email_id
    except Exception as exc:
        print(f"[email] Error enviando a {to_email} desde {from_email}: {exc}")
        return None


def send_all_with_delay(
    rows: list[dict],
    on_sent_callback: Callable[[dict, str, str], None] | None = None,
) -> tuple[int, int]:
    """
    Envía emails uno a uno rotando entre los remitentes configurados.
    Espera SEND_DELAY_MIN–SEND_DELAY_MAX segundos entre cada envío.

    on_sent_callback(row, resend_id, from_email): se llama tras cada envío
    exitoso para persistir el Resend ID antes del siguiente delay.

    Retorna (total_enviados, total_fallidos).
    """
    senders = _get_senders()
    sender_pool = cycle(senders)

    total_sent = 0
    total_failed = 0

    print(f"[email] Remitentes configurados: {', '.join(senders)}")

    for idx, row in enumerate(rows):
        to_email = row.get("Email", "").strip()
        if not to_email:
            total_failed += 1
            continue

        from_email = next(sender_pool)
        print(f"[email] {idx + 1}/{len(rows)} | {from_email} → {to_email}")

        resend_id = send_single_email(row, from_email)

        if resend_id:
            total_sent += 1
            print(f"[email] OK — Resend ID: {resend_id}")
            if on_sent_callback:
                try:
                    on_sent_callback(row, resend_id, from_email)
                except Exception as exc:
                    print(f"[email] Callback post-envío falló: {exc}")
        else:
            total_failed += 1
            print(f"[email] FALLÓ → {to_email}")

        if idx < len(rows) - 1:
            delay = random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX)
            print(f"[email] Esperando {delay / 60:.1f} min antes del siguiente...\n")
            time.sleep(delay)

    return total_sent, total_failed
