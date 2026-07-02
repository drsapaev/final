from __future__ import annotations

from .escpos import escpos_print_text  # noqa: F401

# Conditional import for print module (requires reportlab)
try:
    from .print import build_invoice_pdf, build_ticket_pdf  # noqa: F401
except ImportError:
    # Reportlab not installed - PDF generation will not be available
    build_invoice_pdf = None  # type: ignore
    build_ticket_pdf = None  # type: ignore
