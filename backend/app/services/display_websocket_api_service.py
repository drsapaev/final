"""Service layer for display_websocket endpoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.specialties import canonical_specialty
from app.crud import queue_resource_routing
from app.crud.clinic import get_queue_settings
from app.repositories.display_websocket_api_repository import (
    DisplayWebSocketApiRepository,
)
from app.services.display_websocket import get_display_manager


@dataclass
class DisplayWebSocketApiDomainError(Exception):
    status_code: int
    detail: str


class DisplayWebSocketApiService:
    """Builds payloads and performs queue actions for display websocket API."""

    def __init__(
        self,
        db: Session,
        repository: DisplayWebSocketApiRepository | None = None,
        manager_provider: Callable = get_display_manager,  # type: ignore[type-arg]
    ):
        self.db = db
        self.repository = repository or DisplayWebSocketApiRepository(db)
        self._manager_provider = manager_provider

    def _clinic_today(self) -> date:
        """Codex round-24 P2: the quick-call day — the CLINIC-local date
        (the queue-settings timezone SSOT), not the host-local
        ``date.today()``: queue creation paths (GQL joinQueue, morning
        pre-create, the canonical join flow) stamp the clinic-local day,
        so on the documented UTC runtime with an Asia/Tashkent clinic
        the first five local hours resolved the WRONG surface — the
        quick-call missed that day's resource queue and fell through to
        doctor selection (which excludes the seeded 'Resource' owner)
        returning 404 despite a waiting entry. Unit-stub shape
        (db=None + fake repository, same convention as
        _resolve_registry_surface): the day only flows into the
        stubbed lookups — host today keeps the stubs' contract."""
        if not isinstance(self.db, Session):
            return date.today()
        timezone = ZoneInfo(
            get_queue_settings(self.db).get("timezone", "Asia/Tashkent")
        )
        return datetime.now(timezone).date()

    def _resolve_registry_surface(self, specialty: str) -> object | None:
        """QD-2C (Codex round-11 P1): the (today, tag) registry surface
        for a registry-tag specialty, or None.

        The quick-call route addresses a specialty; for a doctorless
        registry tag the queue IS the (today, tag) surface — the pure
        resource row has no specialist, and the bridged synthetic owner
        holds the Resource role excluded from the doctor selection — so
        the surface must be resolved BEFORE the doctor lookup, otherwise
        the mounted quick-call returns 404 despite waiting patients.
        Non-Session db (unit stubs) keeps the legacy doctor path."""
        if not isinstance(self.db, Session):
            return None
        # Codex round-24 P2: the clinic-local day (see _clinic_today).
        return queue_resource_routing.tag_routes_to_resource(
            self.db, specialty, self._clinic_today()
        )

    @staticmethod
    def _role_name(current_user: object) -> str:
        role = getattr(current_user, "role", "")
        return str(getattr(role, "value", role) or "").strip().lower()

    @staticmethod
    def _same_specialty(left: str | None, right: str | None) -> bool:
        # D-1 canonical vocabulary: compare via canonical_specialty so a
        # doctor stored as 'dentistry' matches a request spelling
        # 'stomatology'/'dental' (the still-live profile key) — exact
        # comparison returned 403 for the dental doctor after 0049
        # (Codex round-4 P1). Lowercasing stays for non-dental values;
        # empty/None equality semantics are preserved.
        def _canon(value: str | None) -> str:
            return (canonical_specialty(str(value or "").strip()) or "").strip().lower()

        return _canon(left) == _canon(right)

    def _current_doctor_or_403(self, current_user: object) -> object:
        doctor = self.repository.get_active_doctor_by_user_id(
            getattr(current_user, "id", None)
        )
        if not doctor:
            raise DisplayWebSocketApiDomainError(
                status_code=403,
                detail="Doctor profile is required to call queue patients",
            )
        return doctor

    def _ensure_doctor_can_call_queue(
        self,
        *,
        current_user: object,
        queue: object,
    ) -> None:
        if self._role_name(current_user) != "doctor":
            return

        doctor = self._current_doctor_or_403(current_user)
        if getattr(queue, "specialist_id", None) != getattr(doctor, "id", None):
            raise DisplayWebSocketApiDomainError(
                status_code=403,
                detail="Doctor can only call patients from their own queue",
            )

    async def call_patient(
        self,
        *,
        entry_id: int,
        board_ids: list[str],
        current_user: object,
    ) -> dict:
        queue_entry = self.repository.get_queue_entry(entry_id)
        if not queue_entry:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail="Запись в очереди не найдена",
            )

        self._ensure_doctor_can_call_queue(
            current_user=current_user,
            queue=queue_entry.queue,
        )

        queue_entry.status = "called"
        queue_entry.called_at = datetime.now(UTC)
        # QF-1 (operator attribution): display-board call surface (covers
        # POST /display/call-patient and /display/quick/call-next — the
        # latter delegates here). getattr: current_user is loosely typed
        # (object) in this service; unknown caller keeps NULL, never
        # fabricates an attribution.
        queue_entry.called_by_user_id = getattr(current_user, "id", None)
        self.repository.save()

        # QD-2C (Codex round-10 P1): resource/bridged очередь
        # (queue_resource_id) — назначение вызова из оси ресурса:
        # имя из реестра, кабинет из строки очереди (persisted
        # default_cabinet / админ-override) с фолбэком на реестр;
        # иначе вызванному пациенту не сообщается кабинет.
        queue = queue_entry.queue
        if getattr(queue, "queue_resource_id", None) is not None:
            resource = getattr(queue, "queue_resource", None)
            doctor_name = resource.display_name if resource is not None else "Врач"
            cabinet = queue.cabinet_number or (
                resource.default_cabinet if resource is not None else None
            )
        else:
            doctor = queue.specialist
            doctor_name = doctor.user.full_name if doctor and doctor.user else "Врач"
            cabinet = doctor.cabinet if doctor else None

        manager = self._manager_provider()
        await manager.broadcast_patient_call(
            queue_entry=queue_entry,
            doctor_name=doctor_name,
            cabinet=cabinet,
            board_ids=board_ids if board_ids else None,
        )

        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван на табло",
            "call_data": {
                "number": queue_entry.number,
                "patient_name": queue_entry.patient_name,
                "doctor": doctor_name,
                "cabinet": cabinet,
                "called_at": queue_entry.called_at.isoformat(),
            },
            "boards_notified": len(board_ids) if board_ids else len(manager.connections),
        }

    def get_department_queue_state_payload(self, *, department: str) -> dict:
        # Codex round-30 P2: день снапшота отделения — clinic_today SSOT
        # (таймзона настроек очередей, см. _clinic_today): соединения и
        # request_update в окне 19:00-24:00Z получали пустой/вчерашний
        # снапшот, пока живые resource-очереди лежали на текущем
        # клиник-локальном дне.
        today = self._clinic_today()
        queue_entries = self.repository.list_active_entries_for_day(day=today)

        filtered_entries = []
        for entry in queue_entries:
            filtered_entries.append(
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                }
            )

        return {
            "type": "queue_state",
            "department": department,
            "timestamp": datetime.now(UTC).isoformat(),
            "entries": filtered_entries,
            "total_waiting": len(
                [entry for entry in filtered_entries if entry["status"] == "waiting"]
            ),
            "current_number": max(
                [entry["number"] for entry in filtered_entries],
                default=0,
            ),
        }

    async def quick_call_next(
        self,
        *,
        specialty: str,
        board_id: str | None,
        current_user: object,
    ) -> dict:
        registry_surface = None
        if self._role_name(current_user) == "doctor":
            doctor = self._current_doctor_or_403(current_user)
            if not self._same_specialty(getattr(doctor, "specialty", None), specialty):
                raise DisplayWebSocketApiDomainError(
                    status_code=403,
                    detail="Doctor can only quick-call patients for their own specialty",
                )
        else:
            doctor = None
            # QD-2C (Codex round-11 P1): registry-tag specialty — the
            # surface first (see _resolve_registry_surface); the
            # doctor selection stays for non-registry specialties.
            registry_surface = self._resolve_registry_surface(specialty)
            if registry_surface is None:
                doctor = self.repository.get_active_doctor_by_specialty(specialty)
            if not doctor and registry_surface is None:
                raise DisplayWebSocketApiDomainError(
                    status_code=404,
                    detail=f"Врач специальности {specialty} не найден",
                )

        if registry_surface is not None:
            daily_queue = registry_surface
        else:
            daily_queue = self.repository.get_daily_queue_for_specialist(
                # Codex round-24 P2: the clinic-local day — the doctor
                # queues are created with it (morning pre-create), the
                # host-local date missed them in the early-morning window.
                day=self._clinic_today(),
                specialist_id=doctor.id,
            )

        if daily_queue:
            self._ensure_doctor_can_call_queue(
                current_user=current_user,
                queue=daily_queue,
            )

        if not daily_queue:
            raise DisplayWebSocketApiDomainError(
                status_code=404,
                detail="Очередь на сегодня не найдена",
            )

        next_entry = self.repository.get_next_waiting_entry(queue_id=daily_queue.id)
        if not next_entry:
            return {
                "success": False,
                "message": "Нет пациентов в очереди",
                "queue_empty": True,
            }

        return await self.call_patient(
            entry_id=next_entry.id,
            board_ids=[board_id] if board_id else [],
            current_user=current_user,
        )
