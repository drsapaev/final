"""Qr_Helpers mixin for QRQueueService.

Split from qr_queue_service.py.
"""
from __future__ import annotations

from app.services.qr_queue._base import *  # noqa: F401, F403
from app.services.qr_queue._base import QRQueueServiceMixinBase


class QrHelpersMixin(QRQueueServiceMixinBase):
    """Qr_Helpers methods for QRQueueService."""

    def _get_frontend_url(self) -> str:
        """
        Определяет URL фронтенда для QR кодов

        Приоритет:
        1. FRONTEND_URL из настроек (если задан явно и не localhost)
        2. Автоматическое определение локального IP (для локальной сети)

        Returns:
            URL вида http://{domain_or_ip}:5173 или https://{domain}
        """
        # Сначала проверяем настройку FRONTEND_URL
        configured_url = settings.FRONTEND_URL

        # Если URL задан явно и это не localhost/127.0.0.1 - используем его
        # Это позволяет задать публичный домен/IP для доступа через интернет
        if configured_url and configured_url not in [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://192.168.1.9:5173",  # Старое значение по умолчанию
        ]:
            logger.debug(
                f"[QRQueueService] Используется FRONTEND_URL из настроек: {configured_url}"
            )
            return configured_url

        # Если не задан явно или это localhost - определяем локальный IP автоматически
        # Это для работы в локальной сети (WiFi)
        try:
            # Создаем временный сокет для определения локального IP
            # Используем подключение к Google DNS (8.8.8.8), но не отправляем данные
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # Подключаемся к внешнему адресу (не отправляем данные)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
            finally:
                s.close()

            frontend_url = f"http://{local_ip}:5173"
            logger.debug(
                f"[QRQueueService] Автоматически определен локальный IP: {frontend_url}"
            )
            return frontend_url
        except Exception as e:
            # Если не удалось определить IP, используем fallback из настроек
            logger.debug(
                f"[QRQueueService] Ошибка определения IP: {e}, используем FRONTEND_URL из настроек: {configured_url}"
            )
            return configured_url or "http://localhost:5173"


    def _generate_qr_code(self, url: str) -> str:
        """Генерирует QR код и возвращает его в base64"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"


