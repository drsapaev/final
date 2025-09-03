from __future__ import annotations


from app.core.config import settings

# Библиотека python-escpos может отсутствовать в окружении — обрабатываем мягко
try:  # pragma: no cover
    from escpos.printer import Network, Usb
except Exception:  # pragma: no cover
    Network = None  # type: ignore
    Usb = None  # type: ignore


def escpos_print_text(text: str, *, cut: bool = True) -> dict:
    """
    Простой печатный вывод текста на ESC/POS принтер.
    Конфигурация берётся из settings: PRINTER_TYPE=none|network|usb
    network: PRINTER_NET_HOST, PRINTER_NET_PORT
    usb: PRINTER_USB_VID, PRINTER_USB_PID
    """
    ptype = (settings.PRINTER_TYPE or "none").lower()

    if ptype == "none":
        # Сухой режим — просто вернуть, что бы было отправлено
        return {
            "ok": True,
            "dry_run": True,
            "text": text,
            "bytes_count": len(text.encode("cp866", errors="ignore")),
        }

    if ptype == "network":
        if Network is None:
            return {"ok": False, "error": "escpos library not available"}
        host = settings.PRINTER_NET_HOST or "127.0.0.1"
        port = int(settings.PRINTER_NET_PORT or 9100)
        try:
            printer = Network(host, port=port, timeout=5)  # type: ignore[call-arg]
            printer.textln(text)  # type: ignore[attr-defined]
            if cut:
                try:
                    printer.cut()  # type: ignore[attr-defined]
                except Exception:
                    pass
            return {"ok": True, "host": host, "port": port}
        except Exception as e:
            return {"ok": False, "error": f"Network ESC/POS error: {e}"}

    if ptype == "usb":
        if Usb is None:
            return {"ok": False, "error": "escpos library not available"}
        if settings.PRINTER_USB_VID is None or settings.PRINTER_USB_PID is None:
            return {"ok": False, "error": "USB VID/PID not configured"}
        try:
            printer = Usb(settings.PRINTER_USB_VID, settings.PRINTER_USB_PID)  # type: ignore[call-arg]
            printer.textln(text)  # type: ignore[attr-defined]
            if cut:
                try:
                    printer.cut()  # type: ignore[attr-defined]
                except Exception:
                    pass
            return {
                "ok": True,
                "vid": settings.PRINTER_USB_VID,
                "pid": settings.PRINTER_USB_PID,
            }
        except Exception as e:
            return {"ok": False, "error": f"USB ESC/POS error: {e}"}

    return {"ok": False, "error": f"Unsupported PRINTER_TYPE={settings.PRINTER_TYPE!r}"}
