"""
dedupe_emails.py — Elimina filas duplicadas por email del sheet de Contactos.

Regla de conservación:
  - Si algún duplicado ya tiene Email Enviado = "Sí", conserva esa fila.
  - Si hay empate (ninguno enviado o varios enviados), conserva la primera ocurrencia.
  - Elimina las demás de abajo hacia arriba para no corromper los índices de fila.

Uso:
  python dedupe_emails.py --dry-run   # solo muestra, no borra
  python dedupe_emails.py             # borra duplicados
  python dedupe_emails.py --limit 50  # procesa hasta 50 grupos duplicados
"""

import argparse
from collections import defaultdict

import gspread
from dotenv import load_dotenv

from sheets_client import _open_worksheet

load_dotenv()


def find_duplicates(ws: gspread.Worksheet) -> dict[str, list[dict]]:
    """
    Retorna un dict { email_normalizado: [ {row_index, row_data}, ... ] }
    solo para emails que aparecen más de una vez.
    Filas sin email son ignoradas.
    """
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return {}

    headers = all_values[0]
    email_idx = headers.index("Email")
    sent_idx = headers.index("Email Enviado")

    groups: dict[str, list[dict]] = defaultdict(list)

    for i, row in enumerate(all_values[1:], start=2):
        email = row[email_idx].strip().lower() if len(row) > email_idx else ""
        if not email:
            continue
        groups[email].append({
            "row_index": i,
            "email_raw": row[email_idx].strip(),
            "nombre": row[headers.index("Nombre")] if "Nombre" in headers else "",
            "sent": row[sent_idx].strip() if len(row) > sent_idx else "",
        })

    return {email: rows for email, rows in groups.items() if len(rows) > 1}


def pick_row_to_keep(rows: list[dict]) -> int:
    """
    Devuelve el row_index de la fila que se debe conservar.
    Prioridad: Email Enviado = "Sí" → primera ocurrencia.
    """
    for row in rows:
        if row["sent"] == "Sí":
            return row["row_index"]
    return rows[0]["row_index"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina filas duplicadas por email.")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra duplicados, no borra.")
    parser.add_argument("--limit", type=int, default=0, help="Máximo de grupos de duplicados a procesar (0 = todos).")
    parser.add_argument("--sheet", default="Contactos", help="Nombre de la hoja de cálculo.")
    args = parser.parse_args()

    ws = _open_worksheet(args.sheet)
    print(f"[dedupe] Cargando sheet '{args.sheet}'...")

    duplicates = find_duplicates(ws)
    total_groups = len(duplicates)
    print(f"[dedupe] Grupos de email duplicado encontrados: {total_groups}")

    if not duplicates:
        print("[dedupe] No hay duplicados. ¡Dataset limpio!")
        return

    if args.limit > 0:
        duplicates = dict(list(duplicates.items())[: args.limit])
        print(f"[dedupe] Procesando solo {len(duplicates)} grupos (--limit {args.limit})")

    rows_to_delete: list[int] = []

    for email, rows in duplicates.items():
        keep = pick_row_to_keep(rows)
        to_delete = [r["row_index"] for r in rows if r["row_index"] != keep]

        keep_info = next(r for r in rows if r["row_index"] == keep)
        print(
            f"\n  Email: {email!r}  ({len(rows)} ocurrencias)"
            f"\n  Conservar → fila {keep} | {keep_info['nombre']!r} | Enviado={keep_info['sent']!r}"
        )
        for r in rows:
            if r["row_index"] in to_delete:
                print(f"  Borrar   → fila {r['row_index']} | {r['nombre']!r} | Enviado={r['sent']!r}")

        rows_to_delete.extend(to_delete)

    total_to_delete = len(rows_to_delete)
    print(f"\n[dedupe] Total de filas a eliminar: {total_to_delete}")

    if args.dry_run:
        print("[dedupe] --dry-run activo. No se borró nada.")
        return

    confirm = input(f"\n¿Confirmas borrar {total_to_delete} filas? [s/N]: ").strip().lower()
    if confirm != "s":
        print("[dedupe] Operación cancelada.")
        return

    # Eliminar de abajo hacia arriba para no desplazar índices
    for row_index in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_index)
        print(f"[dedupe] Fila {row_index} eliminada.")

    print(f"\n[dedupe] Listo. {total_to_delete} filas duplicadas eliminadas.")


if __name__ == "__main__":
    main()
