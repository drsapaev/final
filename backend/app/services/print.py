from __future__ import annotations

from io import BytesIO
from typing import Optional, Sequence, Tuple

from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.core.config import settings


def _try_draw_logo(c: canvas.Canvas, x: float, y: float, w: float) -> None:
    """
    Нарисовать логотип (если указан CLINIC_LOGO_PATH) с шириной w, сохранив пропорции.
    Левая нижняя точка — (x,y).
    """
    path = settings.CLINIC_LOGO_PATH
    if not path:
        return
    try:
        from reportlab.lib.utils import ImageReader  # lazy

        img = ImageReader(path)
        iw, ih = img.getSize()
        if iw <= 0 or ih <= 0:
            return
        scale = w / float(iw)
        h = ih * scale
        c.drawImage(
            img,
            x,
            y,
            width=w,
            height=h,
            mask="auto",
            preserveAspectRatio=True,
            anchor="sw",
        )
    except Exception:
        # Логотип опционален — не роняем генерацию
        pass


def build_ticket_pdf(
    *,
    ticket_number: int,
    department: str,
    clinic_name: Optional[str] = None,
    footer_enabled: Optional[bool] = None,
) -> bytes:
    """
    Сгенерировать PDF талон (A6 портрет). Минимальная вёрстка: номер крупно,
    отделение, дата/время печати и опциональный футер.
    """
    clinic = clinic_name or settings.APP_NAME
    footer = (
        settings.PDF_FOOTER_ENABLED if footer_enabled is None else bool(footer_enabled)
    )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A6)
    W, H = A6  # points

    # Логотип / шапка
    _try_draw_logo(c, 10 * mm, H - 22 * mm, 24 * mm)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(10 * mm, H - 8 * mm, clinic)

    # Заголовок
    c.setFont("Helvetica", 10)
    c.drawString(10 * mm, H - 16 * mm, f"Отделение: {department}")

    # Номер крупно по центру
    c.setFont("Helvetica-Bold", 72)
    num = str(ticket_number)
    tw = c.stringWidth(num, "Helvetica-Bold", 72)
    c.drawString((W - tw) / 2, H / 2 - 36, num)

    # Дата/время печати
    import datetime as _dt

    now = _dt.datetime.now()
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 8 * mm, 12 * mm, now.strftime("%Y-%m-%d %H:%M:%S"))

    if footer:
        c.setFont("Helvetica", 7)
        c.drawCentredString(W / 2, 6 * mm, "Спасибо за обращение!")

    c.showPage()
    c.save()
    return buf.getvalue()


def build_invoice_pdf(
    *,
    visit_id: int,
    items: Sequence[Tuple[str, float, str]] | None = None,
    totals_currency: str = "UZS",
    clinic_name: Optional[str] = None,
    footer_enabled: Optional[bool] = None,
) -> bytes:
    """
    Счет-фактура (A4): простая таблица: Наименование | Сумма | Валюта.
    items: список кортежей (name, amount, currency).
    """
    clinic = clinic_name or settings.APP_NAME
    footer = (
        settings.PDF_FOOTER_ENABLED if footer_enabled is None else bool(footer_enabled)
    )

    rows = list(items or [])
    total = sum(a for _, a, cur in rows if (cur or totals_currency) == totals_currency)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # Шапка
    _try_draw_logo(c, 20 * mm, H - 30 * mm, 32 * mm)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 12 * mm, clinic)
    c.setFont("Helvetica", 12)
    c.drawString(20 * mm, H - 20 * mm, f"Счёт по визиту #{visit_id}")

    # Таблица
    top = H - 40 * mm
    x_name = 20 * mm
    x_amt = 160 * mm
    x_cur = 185 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_name, top, "Наименование")
    c.drawRightString(x_amt, top, "Сумма")
    c.drawString(x_cur, top, "Валюта")
    c.line(20 * mm, top - 3, W - 20 * mm, top - 3)

    y = top - 10 * mm
    c.setFont("Helvetica", 10)
    if not rows:
        c.drawString(x_name, y, "— Нет позиций —")
        y -= 8 * mm
    else:
        for name, amount, currency in rows:
            c.drawString(x_name, y, str(name))
            c.drawRightString(x_amt, y, f"{float(amount):.2f}")
            c.drawString(x_cur, y, str(currency or totals_currency))
            y -= 8 * mm
            if y < 30 * mm:
                c.showPage()
                y = H - 20 * mm

    # Итого
    c.setFont("Helvetica-Bold", 12)
    c.line(120 * mm, y - 3, W - 20 * mm, y - 3)
    y -= 10 * mm
    c.drawRightString(x_amt, y, f"{total:.2f}")
    c.drawString(x_cur, y, totals_currency)
    c.drawString(x_name, y, "ИТОГО")

    # Футер
    if footer:
        c.setFont("Helvetica", 8)
        c.drawCentredString(W / 2, 12 * mm, "Желаем крепкого здоровья!")

    c.showPage()
    c.save()
    return buf.getvalue()
