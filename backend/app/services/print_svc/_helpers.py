"""Helpers mixin for PrintService.

Split from print_service.py.
"""
from __future__ import annotations

from app.services.print_svc._base import *  # noqa: F401, F403
from app.services.print_svc._base import PrintServiceMixinBase  # noqa: F401


class HelpersMixin(PrintServiceMixinBase):
    """Helpers methods."""

    async def discover_system_printers(self) -> list[dict[str, Any]]:
        """Получить список локально установленных принтеров ОС."""
        try:
            system_name = platform.system()
            if system_name == "Windows":
                return await asyncio.to_thread(self._discover_windows_printers_sync)
            if system_name in {"Linux", "Darwin"}:
                return await asyncio.to_thread(self._discover_unix_printers_sync)
            return []
        except Exception as e:
            logger.warning("[FIX] System printer discovery failed: %s", e)
            return []


    async def sync_system_printers(self) -> list[PrinterConfig]:
        """Синхронизировать локальные системные принтеры в БД."""
        discovered = await self.discover_system_printers()
        synced: list[PrinterConfig] = []

        for printer_data in discovered:
            try:
                synced.append(self._upsert_discovered_printer(printer_data))
            except Exception as e:
                logger.warning(
                    "[FIX] Failed to sync discovered printer %s: %s",
                    printer_data.get("name"),
                    e,
                )

        if synced:
            logger.info("[FIX] Synced %s system printers", len(synced))

        return synced


    def _discover_windows_printers_sync(self) -> list[dict[str, Any]]:
        """Обнаружить локальные принтеры в Windows через PowerShell."""
        command = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-Printer | "
                "Select-Object Name,DriverName,PortName,Shared,Default,PrinterStatus,Comment,Location,WorkOffline | "
                "ConvertTo-Json -Depth 4"
            ),
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        raw_output = completed.stdout.strip()
        if not raw_output:
            return []

        payload = json.loads(raw_output)
        items = payload if isinstance(payload, list) else [payload]

        discovered: list[dict[str, Any]] = []
        for item in items:
            normalized = self._normalize_discovered_printer(item, system_name="Windows")
            if normalized:
                discovered.append(normalized)

        return discovered


    def _discover_unix_printers_sync(self) -> list[dict[str, Any]]:
        """Обнаружить локальные принтеры в Unix-подобных системах."""
        command = ["lpstat", "-p"]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError:
            return []

        discovered: list[dict[str, Any]] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("printer "):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            name = parts[1]
            discovered.append(
                self._normalize_discovered_printer(
                    {
                        "Name": name,
                        "DriverName": name,
                        "PortName": name,
                        "Shared": False,
                        "Default": False,
                        "PrinterStatus": 0,
                        "Comment": "",
                        "Location": "",
                        "WorkOffline": False,
                    },
                    system_name="Unix",
                )
            )

        return [item for item in discovered if item]


    def _normalize_discovered_printer(
        self, raw: dict[str, Any], *, system_name: str
    ) -> dict[str, Any] | None:
        """Свести системные данные принтера к нашему внутреннему формату."""
        name = str(
            raw.get("Name")
            or raw.get("name")
            or raw.get("PrinterName")
            or raw.get("displayName")
            or ""
        ).strip()
        if not name:
            return None

        driver_name = str(raw.get("DriverName") or raw.get("driverName") or name).strip()
        port_name = str(raw.get("PortName") or raw.get("portName") or name).strip()
        comment = str(raw.get("Comment") or raw.get("comment") or "").strip()
        location = str(raw.get("Location") or raw.get("location") or "").strip()
        display_name = comment or location or name
        printer_type = self._infer_printer_type(name, driver_name)
        paper_width, paper_height = self._infer_paper_size(printer_type)
        is_default = bool(raw.get("Default") or raw.get("default") or raw.get("isDefault"))
        status = self._infer_printer_status(raw)

        return {
            "name": name,
            "display_name": display_name,
            "printer_type": printer_type,
            "connection_type": "local",
            "device_path": name if system_name == "Windows" else port_name,
            "paper_width": paper_width,
            "paper_height": paper_height,
            "margins": None,
            "encoding": "utf-8",
            "active": True,
            "is_default": is_default,
            "status": status,
            "driver_name": driver_name,
            "location": location,
        }


    def _infer_printer_type(self, name: str, driver_name: str) -> str:
        haystack = f"{name} {driver_name}".lower()

        if any(keyword in haystack for keyword in THERMAL_PRINTER_KEYWORDS):
            return "ESC/POS"

        if any(keyword in haystack for keyword in PRESCRIPTION_PRINTER_KEYWORDS):
            return "A5"

        if any(keyword in haystack for keyword in LAB_PRINTER_KEYWORDS):
            return "A4"

        return "A4"


    def _infer_paper_size(self, printer_type: str) -> tuple[int | None, int | None]:
        if printer_type == "ESC/POS":
            return 58, None
        if printer_type == "A5":
            return 148, 210
        return 210, 297


    def _infer_printer_status(self, raw: dict[str, Any]) -> str:
        if raw.get("WorkOffline") or raw.get("workOffline"):
            return "offline"

        status_value = raw.get("PrinterStatus") or raw.get("printerStatus")
        if isinstance(status_value, str):
            lowered = status_value.lower()
            if lowered in {"offline", "error", "disabled"}:
                return "offline"
            return "online"

        if status_value in {1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}:
            return "offline"

        return "online"


    def _upsert_discovered_printer(
        self, printer_data: dict[str, Any]
    ) -> PrinterConfig:
        """Создать или обновить конфигурацию принтера из системного инвентаря."""
        printer = crud_print.get_printer_by_name(self.db, printer_data["name"])
        if not printer:
            printer = PrinterConfig(
                name=printer_data["name"],
                display_name=printer_data["display_name"],
                printer_type=printer_data["printer_type"],
                connection_type=printer_data["connection_type"],
                device_path=printer_data["device_path"],
                paper_width=printer_data["paper_width"],
                paper_height=printer_data["paper_height"],
                margins=printer_data["margins"],
                encoding=printer_data["encoding"],
                active=printer_data["active"],
                is_default=printer_data["is_default"],
            )
            self.db.add(printer)
        else:
            printer.display_name = printer_data["display_name"]
            printer.printer_type = printer_data["printer_type"]
            printer.connection_type = printer_data["connection_type"]
            printer.device_path = printer_data["device_path"]
            printer.paper_width = printer_data["paper_width"]
            printer.paper_height = printer_data["paper_height"]
            printer.margins = printer_data["margins"]
            printer.encoding = printer_data["encoding"]
            printer.active = True
            printer.is_default = printer_data["is_default"] or printer.is_default

        self.db.commit()
        self.db.refresh(printer)
        return printer


    async def generate_receipt(
        self,
        payment_id: int | None = None,
        visit_id: int | None = None,
        payment_data: dict[str, Any] | None = None,
        printer_name: str | None = None,
        user: User | None = None,
    ) -> dict[str, Any]:
        """
        Генерация чека (SSOT).

        Args:
            payment_id: ID платежа
            visit_id: ID визита
            payment_data: Данные платежа (если нет payment_id/visit_id)
            printer_name: Имя принтера
            user: Пользователь, выполняющий печать

        Returns:
            Dict с результатом печати
        """
        from app.core.config import settings
        from app.models.payment import Payment
        from app.models.visit import Visit
        from app.services.queue_service import queue_service

        # Получаем данные платежа
        if payment_id:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise ValueError(f"Платеж {payment_id} не найден")
            visit_id = payment.visit_id
        elif visit_id:
            payment = (
                self.db.query(Payment)
                .filter(Payment.visit_id == visit_id, Payment.status == "paid")
                .order_by(Payment.created_at.desc())
                .first()
            )
        else:
            payment = None

        # Получаем данные визита
        if visit_id:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")
        else:
            visit = None

        # Формируем данные для чека
        if payment_data:
            receipt_data = payment_data.copy()
        else:
            receipt_data = {}

        clinic_data = receipt_data.get("clinic") or {}
        receipt_data.setdefault(
            "clinic_name",
            receipt_data.get("clinic_name")
            or clinic_data.get("name")
            or settings.APP_NAME,
        )
        receipt_data.setdefault(
            "clinic_phone",
            receipt_data.get("clinic_phone")
            or clinic_data.get("phone")
            or "",
        )
        receipt_data.setdefault(
            "clinic_address",
            receipt_data.get("clinic_address")
            or clinic_data.get("address")
            or "",
        )
        receipt_data.setdefault(
            "clinic_website",
            receipt_data.get("clinic_website")
            or clinic_data.get("website")
            or "",
        )
        receipt_data.setdefault(
            "cashier",
            receipt_data.get("cashier")
            or {"full_name": user.full_name if user else "Система"},
        )
        receipt_data.setdefault(
            "doctor",
            receipt_data.get("doctor")
            or {"full_name": user.full_name if user else "Врач", "specialty_name": "", "cabinet": ""},
        )

        # Дополняем данными из БД
        if payment:
            receipt_data.update(
                {
                    "payment_id": payment.id,
                    "amount": float(payment.amount),
                    "currency": payment.currency or "UZS",
                    "method": payment.method or "cash",
                    "status": payment.status,
                    "receipt_no": payment.receipt_no or f"RCP-{payment.id}",
                    "paid_at": (
                        payment.paid_at.isoformat()
                        if payment.paid_at
                        else queue_service.get_local_timestamp(self.db).isoformat()
                    ),
                    "note": payment.note,
                }
            )

        if visit:
            receipt_data.update(
                {
                    "visit_id": visit.id,
                    "patient_name": getattr(visit, 'patient_name', None)
                    or "Не указано",
                    "patient_phone": getattr(visit, 'patient_phone', None),
                }
            )

        payment_block = receipt_data.setdefault("payment", {})
        if isinstance(payment_block, dict):
            payment_block["services"] = payment_block.get("services") or receipt_data.get("services", [])
            payment_block["method_name"] = payment_block.get("method_name") or "cash"
            payment_block["total"] = payment_block.get("total", receipt_data.get("amount", 0))
            payment_block["subtotal"] = payment_block.get("subtotal", payment_block.get("total", 0))
            payment_block["discount"] = payment_block.get("discount", 0)
            payment_block["paid_amount"] = payment_block.get("paid_amount", payment_block.get("total", 0))
            payment_block["change"] = payment_block.get("change", 0)

        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db).isoformat()
        receipt_data.update(
            {
                "date": now,
                "time": now,
                "issued_by": user.full_name if user else "Система",
            }
        )

        # Печатаем чек
        return await self.print_document(
            document_type="receipt",
            document_data=receipt_data,
            printer_name=printer_name,
            user=user,
        )


    async def generate_ticket(
        self,
        queue_entry_id: int | None = None,
        visit_id: int | None = None,
        ticket_data: dict[str, Any] | None = None,
        printer_name: str | None = None,
        user: User | None = None,
    ) -> dict[str, Any]:
        """
        Генерация талона очереди (SSOT).

        Args:
            queue_entry_id: ID записи в очереди
            visit_id: ID визита
            ticket_data: Данные талона (если нет queue_entry_id/visit_id)
            printer_name: Имя принтера
            user: Пользователь, выполняющий печать

        Returns:
            Dict с результатом печати
        """
        from app.core.config import settings
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.queue_service import queue_service

        # Получаем данные из очереди
        if queue_entry_id:
            queue_entry = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == queue_entry_id)
                .first()
            )
            if not queue_entry:
                raise ValueError(f"Запись очереди {queue_entry_id} не найдена")
        else:
            queue_entry = None

        # Получаем данные визита
        if visit_id:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")
        else:
            visit = None

        # Формируем данные для талона
        if ticket_data:
            ticket_data_final = ticket_data.copy()
        else:
            ticket_data_final = {}

        ticket_data_final.setdefault("clinic_name", settings.APP_NAME)
        ticket_data_final.setdefault("clinic_phone", "")
        ticket_data_final.setdefault("clinic_address", "")

        # Дополняем данными из БД
        if queue_entry:
            ticket_data_final.update(
                {
                    "queue_number": queue_entry.number,
                    "queue_id": queue_entry.queue_id,
                    "patient_name": queue_entry.patient_name or "Не указано",
                    "patient_phone": queue_entry.phone,
                    "doctor_name": getattr(queue_entry, 'doctor_name', None),
                    "specialty_name": getattr(queue_entry, 'specialty_name', None),
                    "source": queue_entry.source or "manual",
                }
            )

        if visit:
            ticket_data_final.update(
                {
                    "visit_id": visit.id,
                    "patient_name": getattr(visit, 'patient_name', None)
                    or ticket_data_final.get("patient_name", "Не указано"),
                    "patient_phone": getattr(visit, 'patient_phone', None)
                    or ticket_data_final.get("patient_phone"),
                }
            )

        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db).isoformat()
        ticket_data_final.update(
            {
                "date": now,
                "time": now,
                "issued_by": user.full_name if user else "Система",
            }
        )

        # Печатаем талон
        return await self.print_document(
            document_type="ticket",
            document_data=ticket_data_final,
            printer_name=printer_name,
            user=user,
        )


    def get_print_template(
        self,
        document_type: str,
        printer_id: int | None = None,
        template_id: int | None = None,
        language: str = "ru",
    ) -> dict[str, Any] | None:
        """
        Получить шаблон печати (SSOT).

        Args:
            document_type: Тип документа (receipt, ticket, prescription, etc.)
            printer_id: ID принтера
            template_id: ID шаблона (если указан, используется он)
            language: Язык шаблона

        Returns:
            Dict с данными шаблона или None
        """
        # Находим шаблон
        template = self._get_template(template_id, document_type, printer_id or 0)

        if not template:
            return None

        return {
            "id": template.id,
            "name": template.name,
            "document_type": template.template_type,
            "printer_id": template.printer_id,
            "template_content": template.template_content,
            "language": template.language or language,
            "is_active": template.active,
            "created_at": (
                template.created_at.isoformat() if template.created_at else None
            ),
            "updated_at": (
                template.updated_at.isoformat() if template.updated_at else None
            ),
        }


    def test_print(self, printer_name: str) -> dict[str, Any]:
        """Тестовая печать"""
        test_data = {
            "clinic_name": "ТЕСТОВАЯ КЛИНИКА",
            "date": datetime.now(),
            "time": datetime.now(),
            "queue_number": "TEST",
            "doctor_name": "Тестовый врач",
            "specialty_name": "Терапия",
            "source": "test",
        }

        return asyncio.run(
            self.print_document(
                document_type="ticket",
                document_data=test_data,
                printer_name=printer_name,
            )
        )


# Глобальный экземпляр сервиса (будет инициализирован в зависимостях)
print_service: PrintService | None = None


def get_print_service() -> PrintService:
    """Получить экземпляр сервиса печати"""
    from app.db.session import SessionLocal
    # Lazy import to avoid circular dependency: ``app.services.print_svc``
    # imports this mixin module before ``PrintService`` is defined.
    from app.services.print_svc import PrintService

    db = SessionLocal()
    return PrintService(db)


