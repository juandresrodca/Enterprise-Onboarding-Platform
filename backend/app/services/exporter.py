"""Audit log export: CSV, JSON and PDF."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from app.models.audit import AuditEntry

_COLUMNS = ["id", "ts", "actor", "actor_role", "action", "target", "status",
            "computer", "source_ip", "details"]


def _rows(entries: list[AuditEntry]) -> list[dict[str, str]]:
    out = []
    for e in entries:
        d = e.model_dump(mode="json")
        d["details"] = json.dumps(e.details, ensure_ascii=False) if e.details else ""
        out.append({c: str(d.get(c) or "") for c in _COLUMNS})
    return out


def to_csv(entries: list[AuditEntry]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_rows(entries))
    return buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens UTF-8 correctly


def to_json(entries: list[AuditEntry]) -> bytes:
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "entries": [e.model_dump(mode="json") for e in entries],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def to_pdf(entries: list[AuditEntry], title: str = "Audit Log Export") -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        0, 6,
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        f" - {len(entries)} entries",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(2)

    headers = ["Time (UTC)", "Actor", "Action", "Target", "Status", "Details"]
    widths = [36, 34, 32, 40, 18, 113]

    def header_row() -> None:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths):
            pdf.cell(w, 6, h, border=0, fill=True)
        pdf.ln()
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Helvetica", "", 8)

    header_row()
    fill = False
    for e in entries:
        details = json.dumps(e.details, ensure_ascii=False) if e.details else ""
        cells = [
            e.ts.strftime("%Y-%m-%d %H:%M:%S"), e.actor, e.action, e.target,
            e.status, details[:160],
        ]
        pdf.set_fill_color(241, 245, 249)
        if pdf.get_y() > 185:
            pdf.add_page()
            header_row()
        for text, w in zip(cells, widths):
            safe = text.encode("latin-1", "replace").decode("latin-1")
            pdf.cell(w, 5.5, safe[:90], border=0, fill=fill)
        pdf.ln()
        fill = not fill

    return bytes(pdf.output())


CONTENT_TYPES = {
    "csv": ("text/csv; charset=utf-8", to_csv),
    "json": ("application/json", to_json),
    "pdf": ("application/pdf", to_pdf),
}
