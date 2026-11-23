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

        # DISPLAYCALL-BE-001 (audit PR #3961 round 30): only a WAITING entry
        # on an ACTIVE queue may transition to called. The display surface is
        # not a queue lifecycle writer: served / cancelled / no_show /
        # diagnostics / in_service / incomplete / already-called tickets can
        # no longer be resurrected into a false TV call, and a closed queue
        # fails closed. The canonical doctor-panel route enforces the same
        # "вызывать можно только waiting" policy.
        if queue_entry.status != "waiting":
            raise DisplayWebSocketApiDomainError(
                status_code=409,
                detail=(
                    f"Вызывать можно только waiting, текущий: {queue_entry.status}"
                ),
            )
        queue = queue_entry.queue
        if getattr(queue, "active", True) is not True:
            raise DisplayWebSocketApiDomainError(
                status_code=409,
                detail="Очередь деактивирована — вызов невозможен",
            )

        # DISPLAYCALL-BE-003 (audit PR #3961 round 30): the transition is an
        # ATOMIC conditional UPDATE keyed on status='waiting' (see
        # repository.claim_waiting_entry). A caller that loses a concurrent
        # claim gets a 409 and never broadcasts a duplicate TV event.
        changed_at = datetime.now(UTC)
        claimed = self.repository.claim_waiting_entry(
            queue_entry,
            called_at=changed_at,
            # QF-1 (operator attribution): display-board call surface (covers
            # POST /display/call-patient and /display/quick/call-next — the
            # latter delegates here). getattr: current_user is loosely typed
            # (object) in this service; unknown caller keeps NULL, never
            # fabricates an attribution.
            called_by_user_id=getattr(current_user, "id", None),
        )
        if not claimed:
            raise DisplayWebSocketApiDomainError(
                status_code=409,
                detail=(
                    "Талон больше не в статусе waiting — конкурентный вызов отклонён"
                ),
            )

        # QD-2C (Codex round-10 P1): resource/bridged очередь
        # (queue_resource_id) — назначение вызова из оси ресурса:
        # имя из реестра, кабинет из строки очереди (persisted
        # default_cabinet / админ-override) с фолбэком на реестр;
        # иначе вызванному пациенту не сообщается кабинет.
        daily_cabinet = getattr(queue, "cabinet_number", None)
        if getattr(queue, "queue_resource_id", None) is not None:
            resource = getattr(queue, "queue_resource", None)
            doctor_name = resource.display_name if resource is not None else "Врач"
            cabinet = daily_cabinet or (
                resource.default_cabinet if resource is not None else None
            )
        else:
            doctor = queue.specialist
            doctor_name = doctor.user.full_name if doctor and doctor.user else "Врач"
            # DailyQueue is the saved clinic-day service location. Its
            # explicit assignment takes precedence over the owner's default,
            # matching the resource-owned call path and preserving D2.
            cabinet = daily_cabinet or (doctor.cabinet if doctor else None)

        manager = self._manager_provider()

        # DISPLAYTARGET-BE-001 (audit PR #3961): REST board_ids arrive as
        # integer DB ids while WS rooms are keyed by the board NAME string.
        # Resolve int ids to their DisplayBoard.name room keys before the
        # broadcast (quick-call passes names as strings — they pass through).
        # Unresolvable ids are reported; an explicit unresolvable request
        # must NOT silently fall back to broadcasting on every live room.
        explicit_targets = bool(board_ids)
        resolved_names: list[str] = []
        unknown_ids: list[int] = []
        if explicit_targets:
            resolved_names, unknown_ids = self.repository.resolve_display_board_targets(
                board_ids
            )
        target_board_ids = resolved_names if explicit_targets else None

        delivery_raw = await manager.broadcast_patient_call(
            queue_entry=queue_entry,
            doctor_name=doctor_name,
            cabinet=cabinet,
            board_ids=target_board_ids,
        )
        # Injected managers (tests) may return mocks; only real dicts count.
        delivery = delivery_raw if isinstance(delivery_raw, dict) else {}

        # DISPLAYDELIVERY-BE-001 (audit PR #3961): the queue transition stays
        # committed regardless of transport; the display verdict is reported
        # separately and honestly. boards_notified counts ONLY boards with a
        # live local delivery — never the raw request count.
        boards_notified = sum(
            1 for status in delivery.values() if status == "delivered_local"
        )
        status_set = set(delivery.values())
        if explicit_targets and not resolved_names:
            display_delivery = "failed"
        elif not delivery:
            display_delivery = "unknown"
        elif status_set == {"delivered_local"}:
            display_delivery = "delivered"
        elif status_set == {"failed"}:
            display_delivery = "failed"
        elif "failed" in status_set:
            display_delivery = "partial"
        else:
            # published_only present without failures: cross-worker
            # delivery is unverifiable from here (no ACK semantics).
            display_delivery = "unknown"

        response: dict = {
            "success": True,
            "call_committed": True,
            "message": f"Пациент #{queue_entry.number} вызван на табло",
            "call_data": {
                "number": queue_entry.number,
                "patient_name": queue_entry.patient_name,
                "doctor": doctor_name,
                "cabinet": cabinet,
                "called_at": (queue_entry.called_at or changed_at).isoformat(),
            },
            "boards_requested": len(resolved_names)
            if explicit_targets
            else len(delivery),
            "boards_notified": boards_notified,
            "display_delivery": display_delivery,
            "board_delivery": delivery,
        }
        if unknown_ids:
            response["unknown_board_ids"] = unknown_ids
        return response

    def get_department_queue_state_payload(self, *, department: str) -> dict:
        # Codex round-30 P2: день снапшота отделения — clinic_today SSOT
        # (таймзона настроек очередей, см. _clinic_today): соединения и
        # request_update в окне 19:00-24:00Z получали пустой/вчерашний
        # снапшот, пока живые resource-очереди лежали на текущем
        # клиник-локальном дне.
        today = self._clinic_today()
        # DISPLAYWS-BE-003 (audit PR #3961 round 30): the snapshot is scoped
        # to the REQUESTED department (registry-tag axis + doctor-specialty
        # axis, dental family included). The old day-only listing serialized
        # every active queue of the day under the requested label —
        # /ws/queue/cardiology answered with laboratory and dental patients
        # and wrong totals.
        queue_entries = self.repository.list_active_entries_for_department(
            day=today, department=department
        )

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
                doctor = self.repository.get_active_doctor_by_specialty(
                    # DISPLAYQUICK-BE-001 (audit PR #3961): the least-loaded
                    # chooser must count the SAME clinic-local day the queue
                    # lookup uses below (queue-settings timezone SSOT) — the
                    # host-local date disagreed across the clinic midnight.
                    specialty,
                    day=self._clinic_today(),
                )
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
