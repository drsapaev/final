from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import settings
from app.crud.visit import get_visit_by_id  # type: ignore[attr-defined]

router = APIRouter(prefix="/print", tags=["print"])


@router.get("/ticket.pdf", response_class=Response, summary="Печать талона очереди (PDF)")
async def ticket_pdf(
    department: str = Query(..., min_length=1, max_length=64),
    ticket_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)

    W, H = A5
    y = H - 20 * mm

    if settings.CLINIC_LOGO_PATH:
        try:
            c.drawImage(settings.CLINIC_LOGO_PATH, 15 * mm, y - 20 * mm, width=30 * mm, height=20 * mm, preserveAspectRatio=True)
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 22)
    c.drawString(15 * mm, y, settings.APP_NAME)
    y -= 12 * mm

    c.setFont("Helvetica", 14)
    c.drawString(15 * mm, y, f"Отделение: {department}")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 48)
    c.drawString(15 * mm, y, f"№ {ticket_number}")
    y -= 20 * mm

    if settings.PDF_FOOTER_ENABLED:
        c.setFont("Helvetica", 10)
        c.drawRightString(W - 15 * mm, 10 * mm, f"{settings.APP_VERSION} — {settings.ENV}")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    return Response(content=pdf, media_type="application/pdf")


@router.get("/invoice.pdf", response_class=Response, summary="Счёт/квитанция на оплату (PDF)")
async def invoice_pdf(
    visit_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Cashier")),
):
    visit = get_visit_by_id(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    W, H = A4
    y = H - 20 * mm

    if settings.CLINIC_LOGO_PATH:
        try:
            c.drawImage(settings.CLINIC_LOGO_PATH, 15 * mm, y - 20 * mm, width=30 * mm, height=20 * mm, preserveAspectRatio=True)
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, y, settings.APP_NAME)
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(15 * mm, y, f"Счёт на оплату (Визит #{visit['id']})")
    y -= 10 * mm

    c.setFont("Helvetica", 12)
    c.drawString(15 * mm, y, f"Пациент: {visit.get('patient_full_name') or visit.get('patient_id')}")
    y -= 7 * mm
    c.drawString(15 * mm, y, f"Дата визита: {visit.get('visit_date') or ''}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Услуги:")
    y -= 7 * mm

    c.setFont("Helvetica", 11)
    total = 0.0
    for item in visit.get("services", []):
        name = item.get("name") or item.get("code") or "—"
        price = float(item.get("price") or 0.0)
        total += price
        c.drawString(20 * mm, y, name)
        c.drawRightString(W - 20 * mm, y, f"{price:.2f} {item.get('currency') or 'UZS'}")
        y -= 6 * mm

    y -= 3 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - 20 * mm, y, f"Итого: {total:.2f} UZS")

    if settings.PDF_FOOTER_ENABLED:
        c.setFont("Helvetica", 10)
        c.drawRightString(W - 15 * mm, 10 * mm, f"{settings.APP_VERSION} — {settings.ENV}")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    return Response(content=pdf, media_type="application/pdf")