"""
Сервис утренней сборки для присвоения номеров в очередях
Запускается каждое утро для обработки подтвержденных визитов на текущий день
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.crud.clinic import clinic_today as _clinic_today
from app.crud.queue_owner_policy import (
    QueueOwnerConfigurationError,
    eligible_real_doctor,
    owner_configuration_error,
    single_active_service_doctor,
)
from app.crud.queue_resource_routing import (
    find_active_tag_queue,
    lock_queue_tag_claim_scope,
    resolve_tag_resource,
)
from app.db.session import SessionLocal
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.queue_claim_service import (
    QueueClaimConflictError,
    lock_and_resolve_active_tag_claim,
)
from app.services.queue_service import queue_service
from app.services.service_mapping import get_service_code

logger = logging.getLogger(__name__)


class MorningAssignmentClaimError(QueueOwnerConfigurationError):
    """A conflicting claim that must abort wizard and batch assignment."""


@dataclass(frozen=True)
class MorningAssignmentCreateBranchHandoff:
    """Wizard-local handoff for the create-entry branch."""

    queue_tag: str
    daily_queue: DailyQueue
    create_entry_kwargs: dict[str, Any]

    def build_assigned_payload(self, *, number: int) -> dict[str, Any]:
        return {
            "queue_tag": self.queue_tag,
            "queue_id": self.daily_queue.id,
            "number": number,
            "status": "assigned",
        }


@dataclass(frozen=True)
class MorningAssignmentPreparedQueueAssignment:
    assignment: dict[str, Any] | None = None
    create_handoff: MorningAssignmentCreateBranchHandoff | None = None


class MorningAssignmentService:
    """Сервис утренней сборки для присвоения номеров в очередях"""

    def __init__(self, db: Session | None = None):
        self.db: Session | None = db
        self._owns_session = db is None

    def __enter__(self):
        if self.db is None:
            self.db = SessionLocal()
            self._owns_session = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db and self._owns_session:
            self.db.close()

    def ensure_daily_queues_for_all_tags(self, target_date: date) -> int:
        """
        ⭐ PHASE 2: Pre-create DailyQueues for all unique Service.queue_tag values.
        This ensures queues exist BEFORE any registration/editing happens,
        preventing race conditions and silent fallbacks.

        Returns: number of queues created/verified
        """
        # Get all unique non-null queue_tags from active services.
        # QD-2E P1: the DISTINCT result order is not defined (PostgreSQL
        # returns an arbitrary order), and pre-create takes a (day, tag)
        # advisory lock per created queue — the tags MUST be processed in
        # sorted order so two concurrent pre-create phases can never take
        # the scopes A→B and B→A (deadlock).
        unique_tags = (
            self.db.query(Service.queue_tag)
            .filter(Service.active == True, Service.queue_tag.isnot(None))
            .distinct()
            .all()
        )
        ordered_tags = sorted(tag for (tag,) in unique_tags)

        created_count = 0

        # QD-2E (RQ-15.b): fail-closed pre-create. The general_resource
        # default doctor (and its any-active-doctor fallback) is GONE —
        # D-08 forbids both. A non-registry tag is pre-created ONLY when
        # it proves an explicit owner: the single distinct doctor on
        # the tag's active services. Zero owners (an undecided operator
        # map surface) or two or more (the PR-26 per-doctor contract)
        # means NO pre-created queue: the tag is skipped with a loud
        # error log, and the booking surfaces raise the explicit
        # configuration error when a patient actually arrives.

        for queue_tag in ordered_tags:
            try:
                # QD-2C runtime switch: тег со строкой в queue_resources
                # (сиды 0059 — lab/ecg) пре-создается на РЕСУРСНОЙ оси:
                # specialist NULL + queue_resource_id. QD-2E: тегам БЕЗ
                # строки реестра синтетик больше не назначается (D-08).
                if resolve_tag_resource(self.db, queue_tag) is not None:
                    if find_active_tag_queue(self.db, target_date, queue_tag) is None:
                        # Codex round-24 P2: изоляция тега в SAVEPOINT — как
                        # легаси-ветка ниже: get_or_create_daily_queue больше
                        # НЕ откатывает сеанс при сбое flush (контракт #3092
                        # P1), поэтому без savepoint сбойнувший тег оставлял
                        # бы полусозданную очередь/счётчик врал бы после
                        # catch-and-continue.
                        with self.db.begin_nested():
                            queue_service.get_or_create_daily_queue(
                                self.db,
                                day=target_date,
                                specialist_id=None,
                                queue_tag=queue_tag,
                            )
                        created_count += 1
                        logger.info(
                            "✅ Pre-created resource DailyQueue for queue_tag=%s",
                            queue_tag,
                        )
                    continue

                # QD-2E (RQ-15.b): единственный явный владелец негегистрового
                # тега — единственный врач его активных услуг (K01/K11 →
                # кардиолог после применения operator map). 0 или ≥2 врачей
                # → тег НЕ пре-создается, громкий лог ошибки (fail-closed).
                tag_owner_id = single_active_service_doctor(self.db, queue_tag)
                if tag_owner_id is None:
                    logger.error(
                        "QD-2E fail-closed: queue_tag=%s has no explicit owner "
                        "(no ACTIVE queue_resources row, no single active "
                        "service doctor) — the general_resource fallback is "
                        "retired (D-08); the queue is NOT pre-created; assign "
                        "a doctor, retag to an active resource or disable the "
                        "service (operator map RQ-15.b)",
                        queue_tag,
                    )
                    continue

                # Check if queue already exists for this tag on this day
                existing = (
                    self.db.query(DailyQueue)
                    .filter(
                        DailyQueue.day == target_date,
                        DailyQueue.queue_tag == queue_tag,
                        DailyQueue.active == True,
                    )
                    .first()
                )

                if not existing:
                    # Create new DailyQueue for this tag
                    # Codex R15 #3092 (P2): изоляция тега в SAVEPOINT. Полный
                    # откат сеанса в except-ветке стирал очереди, созданные
                    # ПРЕДЫДУЩИМИ итерациями этого вызова, а created_count их
                    # уже учёл — отчёт «создано N» расходился с реальностью и
                    # ломал гарантию pre-creation. SAVEPOINT откатывает только
                    # работу сбойнувшего тега: предыдущие создания остаются в
                    # внешней транзакции, счётчик остаётся честным.
                    with self.db.begin_nested():
                        queue_service.get_or_create_daily_queue(
                            self.db,
                            day=target_date,
                            specialist_id=tag_owner_id,
                            queue_tag=queue_tag,
                        )
                    created_count += 1
                    logger.info(
                        "✅ Pre-created DailyQueue for queue_tag=%s on doctor_id=%s",
                        queue_tag,
                        tag_owner_id,
                    )

            except Exception as e:
                # Codex R3 #3092 (P1): get_or_create_daily_queue no longer
                # rolls the session back on flush failure (the rollback erased
                # the atomic cart's uncommitted rows in the wizard flow).
                # Codex R15 #3092 (P2): полный rollback здесь больше не нужен
                # И ВРЕДЕН — сбойнувший тег уже откатен своим SAVEPOINT, а
                # полный откат стирал бы очереди предыдущих тегов этого
                # вызова. Skip-tag-and-continue сохранён без побочных потерь.
                logger.error(f"Error pre-creating queue for {queue_tag}: {e}")

        if created_count > 0:
            # Keep the explicit flush: direct (non-run_morning_assignment)
            # callers rely on the rows being visible in their session with
            # autoflush off; run_morning_assignment commits right after
            # this anyway (QD-2E P1 short pre-create transaction).
            self.db.flush()
            logger.info(
                f"🏗️ Pre-created {created_count} DailyQueues for {len(ordered_tags)} unique queue_tags"
            )

        return created_count

    def run_morning_assignment(self, target_date: date | None = None) -> dict[str, any]:
        """
        Основная функция утренней сборки
        Присваивает номера всем подтвержденным визитам на указанную дату

        QD-2E P1 (транзакционная граница; заменяет прежний P2-1 контракт
        «один commit на весь batch»):

        1. Pre-create — отдельная КОРОТКАЯ транзакция: теги в sorted-порядке,
           commit (или rollback) выполняется НЕМЕДЛЕННО после фазы, поэтому
           (day, tag) advisory-lock-и pre-create не переживают фазу визитов
           и не блокируют QR/GraphQL/подтверждение на всё время сборки.
        2. Визиты — одна атомарная транзакция НА ВИЗИТ: визит перечитывается
           под with_for_update, покрытие перепроверяется, все его (day, tag)
           scope-ы берутся в sorted-порядке ДО routing/owner lookup/write,
           успешный визит коммитится сразу, ошибка откатывает ТОЛЬКО его.
           Счётчики результата описывают durable-состояние БД: визиты,
           закоммиченные до сбоя, остаются закоммиченными и посчитанными.
        """
        if not target_date:
            target_date = _clinic_today(self.db)

        logger.info(f"🌅 Запуск утренней сборки для {target_date}")

        processed_count = 0
        assigned_queues_count = 0
        errors: list[str] = []

        try:
            # ⭐ PHASE 2 + QD-2E P1: pre-create DailyQueues for all
            # Service.queue_tag values in a SHORT dedicated transaction,
            # committed (or rolled back) BEFORE any visit is processed.
            # Pre-create takes (day, tag) advisory locks inside
            # get_or_create_daily_queue; holding them until a single
            # end-of-batch commit (the old P2-1 boundary) blocked every
            # QR/GraphQL/confirmation writer on those tags for the whole
            # batch. The unconditional commit also ends the phase
            # deterministically even when nothing was created.
            try:
                precreated_count = self.ensure_daily_queues_for_all_tags(target_date)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            if precreated_count > 0:
                logger.info(f"🏗️ Pre-created {precreated_count} missing DailyQueues")

            # QD-2E P1: read-only ID worklist — NO with_for_update here.
            # Every visit is re-locked and re-checked inside its own
            # transaction by _process_visit_in_own_transaction.
            candidate_visit_ids = self._get_confirmed_visit_ids_without_queues(
                target_date
            )

            if not candidate_visit_ids:
                logger.info(
                    f"✅ Нет подтвержденных визитов без номеров на {target_date}"
                )
                return {
                    "success": True,
                    "message": f"Нет визитов для обработки на {target_date}",
                    "processed_visits": 0,
                    "assigned_visits": 0,
                    "assigned_queues": 0,
                    "total_queue_entries": 0,
                    "errors": [],
                    "date": target_date.isoformat(),
                }

            logger.info(
                f"📋 Найдено {len(candidate_visit_ids)} подтвержденных визитов для обработки"
            )

            config_error_message: str | None = None

            for visit_id in candidate_visit_ids:
                try:
                    queue_assignments = self._process_visit_in_own_transaction(
                        visit_id, target_date
                    )
                    if queue_assignments:
                        processed_count += 1
                        assigned_queues_count += len(queue_assignments)

                        logger.info(
                            f"✅ Визит {visit_id}: присвоено {len(queue_assignments)} номеров"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Визит {visit_id}: не удалось присвоить номера"
                        )

                except QueueOwnerConfigurationError as config_error:
                    # QD-2E (RQ-15.b + P1): конфиг-ошибка владельца — НЕ
                    # «внутренняя ошибка»: собиравшаяся тишина (errors +=
                    # generic + success: True) вернула бы баг-класс QD-0
                    # пакетно. Откатывается ТОЛЬКО транзакция текущего
                    # визита; визиты, закоммиченные до него, остаются
                    # durable — счётчики ниже честные. Сборка падает
                    # громко: оператор чинит конфигурацию (assign_doctor /
                    # retag_resource / disable_service) и перезапускает.
                    self.db.rollback()
                    logger.error(
                        "QD-2E fail-closed: queue owner configuration error "
                        "for visit %s: %s — aborting the morning assignment",
                        visit_id,
                        config_error,
                    )
                    config_error_message = str(config_error)
                    break

                except Exception:
                    # QD-2E P1: generic failure rolls back ONLY the current
                    # visit's transaction and records a sanitized error
                    # (no patient identifiers); the batch continues.
                    self.db.rollback()
                    error_msg = "Внутренняя ошибка"
                    logger.error(error_msg)
                    errors.append(error_msg)

            if config_error_message is not None:
                # Честный fail-closed отчёт: success=False с причиной, но
                # счётчики описывают durable DB state (что реально
                # закоммичено до сбоя), а не нули.
                return {
                    "success": False,
                    "message": (
                        "QD-2E fail-closed: queue owner configuration error "
                        f"— {config_error_message} (почините владельца и "
                        "перезапустите сборку)"
                    ),
                    "processed_visits": processed_count,
                    "assigned_visits": processed_count,
                    "assigned_queues": assigned_queues_count,
                    "total_queue_entries": assigned_queues_count,
                    "errors": [config_error_message],
                    "date": target_date.isoformat(),
                }

            result = {
                "success": True,
                "message": f"Утренняя сборка завершена для {target_date}",
                "processed_visits": processed_count,
                "assigned_visits": processed_count,
                "assigned_queues": assigned_queues_count,
                "total_queue_entries": assigned_queues_count,
                "errors": errors,
                "date": target_date.isoformat(),
            }

            logger.info(
                f"🎉 Утренняя сборка завершена: {processed_count} визитов, {assigned_queues_count} номеров"
            )
            return result

        except Exception as e:
            # Катастрофический сбой вне per-visit цикла (commit pre-create,
            # worklist-снапшот, ...). QD-2E P1: счётчики описывают durable
            # DB state — визиты, закоммиченные до сбоя, остаются
            # закоммиченными и посчитанными.
            self.db.rollback()
            error_msg = f"Критическая ошибка утренней сборки: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "processed_visits": processed_count,
                "assigned_visits": processed_count,
                "assigned_queues": assigned_queues_count,
                "total_queue_entries": assigned_queues_count,
                "errors": errors,
                "date": target_date.isoformat(),
            }

    def run_assignment_job(self, target_date: date | None = None) -> dict[str, any]:
        """
        Backward-compatible wrapper used by legacy tests/callers.
        """
        result = self.run_morning_assignment(target_date)
        result.setdefault("assigned_visits", result.get("processed_visits", 0))
        result.setdefault("total_queue_entries", result.get("assigned_queues", 0))
        return result

    def _get_confirmed_visit_ids_without_queues(self, target_date: date) -> list[int]:
        """Read-only worklist of confirmed visit IDs missing queue coverage.

        QD-2E P1: the morning batch no longer opens ONE transaction with
        with_for_update() over every confirmed visit (those row locks
        lived until the final batch commit and blocked concurrent
        operators for the whole run). This snapshot takes NO locks;
        each visit is re-locked and re-checked inside its own
        transaction by ``_process_visit_in_own_transaction``.
        """
        visits = self._get_confirmed_visits_without_queues(
            target_date, for_update=False
        )
        return [visit.id for visit in visits]

    def _process_visit_in_own_transaction(
        self,
        visit_id: int,
        target_date: date,
        *,
        source: str = "morning_assignment",
    ) -> list[dict[str, any]]:
        """One atomic transaction for exactly one morning-batch visit.

        QD-2E P1 contract (see run_morning_assignment):

        - the visit row is re-read with FOR UPDATE inside THIS
          transaction (the concurrent-run protection REG-AUDIT-28 P0-1
          moved from the old whole-batch lock);
        - the coverage condition is re-checked under that row lock;
        - a visit that yields no assignments is rolled back and never
          activated;
        - a successful visit (queue entries + activate_confirmed_visit)
          is committed immediately — one commit per visit;
        - any error propagates: the caller rolls back only this visit's
          transaction and keeps the already-committed visits durable.
        """
        visit = (
            self.db.query(Visit)
            .filter(
                Visit.id == visit_id,
                Visit.visit_date == target_date,
                Visit.status == "confirmed",
                Visit.confirmed_at.isnot(None),
            )
            .with_for_update()
            .first()
        )
        if visit is None:
            # Обработан конкурирующим запуском или состояние изменилось
            # после снятия worklist-снапшота — тихий пропуск.
            self.db.rollback()
            logger.info(
                "Визит %s больше не подтвержден на %s — пропуск",
                visit_id,
                target_date,
            )
            return []
        if not self._visit_needs_queue_coverage(visit, target_date):
            # Полное покрытие уже создано конкурирующим писателем.
            self.db.rollback()
            return []

        queue_assignments = self._assign_queues_for_visit(
            visit, target_date, source=source
        )
        if not queue_assignments:
            # Ничего не создано (внутренний per-tag catch уже откатил
            # транзакцию визита) — завершаем её без записи.
            self.db.rollback()
            return []

        # Issue #06 Phase 3: delegate to VisitLifecycleService.
        # activate_confirmed_visit() does confirmed → open.
        # This is a system-initiated transition (batch job),
        # so current_user is None.
        #
        # P2-1: commit=False is MANDATORY — the QD-2E P1 per-visit commit
        # below persists entries + activation atomically; a commit inside
        # the lifecycle service would break the composition contract.
        from app.services.visit_lifecycle_service import (
            VisitLifecycleService,
        )

        VisitLifecycleService(self.db).activate_confirmed_visit(
            visit_id=visit.id,
            commit=False,
        )

        # QD-2E P1: один commit на успешный визит — записи очереди и
        # активация становятся durable вместе или никак.
        self.db.commit()
        return queue_assignments

    def _visit_needs_queue_coverage(self, visit: Visit, target_date: date) -> bool:
        """Проверяет, что у визита ещё нет записей в очередях на дату.

        Тот же предикат, что использовал batch-фильтр: записей нет вовсе
        или существующие записи не покрывают все queue_tag визита.
        """
        existing_queue_entries = (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == visit.patient_id)
            .join(DailyQueue)
            .filter(DailyQueue.day == target_date)
            .all()
        )

        if not existing_queue_entries:
            return True

        visit_queue_tags = self._get_visit_queue_tags(visit)
        existing_queue_tags = set()

        for entry in existing_queue_entries:
            queue = (
                self.db.query(DailyQueue)
                .filter(DailyQueue.id == entry.queue_id)
                .first()
            )
            if queue and queue.queue_tag:
                existing_queue_tags.add(queue.queue_tag)

        return not visit_queue_tags.issubset(existing_queue_tags)

    def _get_confirmed_visits_without_queues(
        self, target_date: date, *, for_update: bool = True
    ) -> list[Visit]:
        """Получает подтвержденные визиты на указанную дату без номеров в очередях

        REG-AUDIT-28 P0-1: ``with_for_update()`` (default) protects the
        read-modify-write callers (the manual API listing) from duplicate
        entries when two operators run the assignment concurrently.
        QD-2E P1: the morning batch itself passes ``for_update=False`` —
        it only builds the ID worklist and re-locks each visit inside
        its own per-visit transaction.
        """

        # Находим визиты со статусом "confirmed" на указанную дату
        query = self.db.query(Visit).filter(
            and_(
                Visit.visit_date == target_date,
                Visit.status == "confirmed",
                Visit.confirmed_at.isnot(None),
            )
        )
        if for_update:
            query = query.with_for_update()
        confirmed_visits = query.all()

        # Фильтруем визиты, у которых еще нет записей в очередях
        visits_without_queues = []
        for visit in confirmed_visits:
            if self._visit_needs_queue_coverage(visit, target_date):
                visits_without_queues.append(visit)
        return visits_without_queues

    def _get_visit_queue_tags(self, visit: Visit) -> set:
        """Получает все queue_tag для услуг визита"""
        # ✅ ИСПРАВЛЕНО: Явный импорт для избежания проблем с циклическими зависимостями
        from app.models.visit import VisitService

        visit_services = (
            self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        queue_tags = set()
        for vs in visit_services:
            service = self.db.query(Service).filter(Service.id == vs.service_id).first()
            if service and service.queue_tag:
                queue_tags.add(service.queue_tag)

        return queue_tags

    def _assign_queues_for_visit(
        self,
        visit: Visit,
        target_date: date,
        source: str = "morning_assignment",
    ) -> list[dict[str, any]]:
        """Присваивает номера в очередях для конкретного визита

        P2-1b (post-merge stabilization): the original code called
        self.db.rollback() on per-queue_tag failure, which discarded ALL
        staged work AND left stale dicts in queue_assignments. The loop
        continued, and the visit was activated with stale data (non-empty
        queue_assignments but 0 real DB entries).

        Fix: on failure, rollback restores the session, then
        queue_assignments is CLEARED to remove stale dicts. The loop
        BREAKS — no further tags are attempted. The visit is NOT
        activated (queue_assignments is empty).

        Trade-off: a single tag failure causes the entire visit's queue
        assignment to fail (no partial assignment). This is more
        conservative than the savepoint approach but avoids conflicts
        with test infrastructure that uses begin_nested() for test
        isolation. Partial assignment support can be added later with
        proper savepoint-aware test infrastructure.

        QD-2E P1: все (day, queue_tag) scope-ы визита берутся В SORTED
        порядке ДО первого routing/owner lookup/write — место, где раньше
        начинался перебор неупорядоченного set. Claim-координатор внутри
        prepare берёт тот же transaction-scoped lock повторно (idempotent
        пока держится), поэтому обработка тегов визита ниже не может
        взять два scope-а в порядке, который конкурирующий single-tag
        writer (QR/GraphQL/подтверждение) инвертирует в deadlock.
        """

        # Получаем уникальные queue_tag из услуг визита
        unique_queue_tags = self._get_visit_queue_tags(visit)

        if not unique_queue_tags:
            logger.warning(f"Визит {visit.id}: нет queue_tag в услугах")
            return []

        ordered_queue_tags = sorted(unique_queue_tags)
        for queue_tag in ordered_queue_tags:
            lock_queue_tag_claim_scope(self.db, queue_tag, target_date)

        queue_assignments = []

        for queue_tag in ordered_queue_tags:
            try:
                assignment = self._assign_single_queue(
                    visit,
                    queue_tag,
                    target_date,
                    source=source,
                )
                if assignment:
                    queue_assignments.append(assignment)
            except QueueOwnerConfigurationError:
                # QD-2E (RQ-15.b): конфигурационная ошибка владельца —
                # НЕ transient-сбой визита: тишина здесь возвращает
                # корневую проблему QD-0 (пациент без номера, никто не
                # знает почему). Ошибка пробивается наверх — утренняя
                # сборка падает громко, оператор чинит конфигурацию
                # (assign_doctor / retag_resource / disable_service)
                # и перезапускает. Откат здесь не нужен: транзакцию
                # откатит вызывающая поверхность.
                logger.error(
                    "QD-2E fail-closed: queue owner configuration error "
                    "for queue_tag=%s visit_id=%s — re-raise (D-08)",
                    queue_tag,
                    visit.id,
                )
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка присвоения очереди {queue_tag} для визита {visit.id}: {e}",
                    exc_info=True,
                )
                # P2-1b: rollback to restore the session after flush failure.
                # No try/except — if rollback fails, the error should propagate.
                self.db.rollback()
                # P2-1b: CLEAR stale data. The rollback destroyed all
                # flushed entries, so any dicts in queue_assignments
                # reference non-existent DB rows. Without clearing, the
                # caller would see non-empty queue_assignments and
                # activate the visit with 0 real queue entries.
                queue_assignments.clear()
                # BREAK — after a full rollback, the session state is
                # reset. Continuing the loop would re-query stale data.
                break

        return queue_assignments

    def _assign_single_queue(
        self,
        visit: Visit,
        queue_tag: str,
        target_date: date,
        *,
        source: str = "morning_assignment",
    ) -> dict[str, any] | None:
        """Assign one queue number through the explicit wizard create-branch handoff."""

        prepared_assignment = self.prepare_wizard_queue_assignment(
            visit,
            queue_tag,
            target_date,
            source=source,
        )
        if prepared_assignment is None:
            return None

        if prepared_assignment.assignment is not None:
            return prepared_assignment.assignment

        create_handoff = prepared_assignment.create_handoff
        if create_handoff is None:
            return None

        queue_entry = queue_service.create_queue_entry(
            self.db,
            **create_handoff.create_entry_kwargs,
        )

        service_codes_for_entry = create_handoff.create_entry_kwargs.get(
            "service_codes", []
        )
        logger.info(
            "Assigned number %s in queue %s through SSOT, services: %s",
            queue_entry.number,
            queue_tag,
            service_codes_for_entry,
        )

        return create_handoff.build_assigned_payload(number=queue_entry.number)

    def prepare_wizard_queue_assignment(
        self,
        visit: Visit,
        queue_tag: str,
        target_date: date,
        *,
        source: str = "morning_assignment",
    ) -> MorningAssignmentPreparedQueueAssignment | None:
        """Присваивает номер в конкретной очереди"""

        # Определяем врача для очереди
        doctor_id = visit.doctor_id
        doctor = None

        if doctor_id:
            doctor = self.db.query(Doctor).filter(Doctor.id == doctor_id).first()
            if not doctor:
                logger.warning(
                    f"Врач с ID {doctor_id} не найден для queue_tag={queue_tag}, visit_id={visit.id}; используем fallback"
                )
                doctor_id = None

        # QD-2C runtime switch: тег со строкой в queue_resources (сиды
        # 0059 — lab/ecg) маршрутизируется на РЕСУРСНУЮ ось без
        # резолва синтетика: get_or_create_daily_queue найдёт/создаст
        # ресурсную очередь (specialist_id для тегов реестра
        # игнорируется — см. queue_svc/_operations.py).
        # QD-2E (RQ-15.b): universal fallback на general_resource для
        # тегов без реестра УДАЛЁН (D-08) — явные источники владельца
        # ниже: (1) единственный врач услуг тега в ЭТОМ визите,
        # (2) переиспользование уже открытой поверхности тега/дня;
        # иначе — конфигурационная ошибка, не тихий None.
        registry_resource = resolve_tag_resource(self.db, queue_tag)
        registry_tag = registry_resource is not None
        if registry_tag:
            # Resource routing is tag-owned even when the visit also carries a
            # doctor.  ``get_or_create_daily_queue`` applies the same rule; do
            # not validate a resource claim against the visit doctor first.
            doctor_id = None
            doctor = None
            logger.info(
                "queue_tag=%s routes to the queue resource axis (QD-2C)",
                queue_tag,
            )

        if not doctor_id and not registry_tag:
            # QD-2E (RQ-15.b): явный владелец из услуг ЭТОГО визита —
            # единственный distinct врач среди активных услуг визита с
            # этим тегом (K01 → кардиолог после применения operator
            # map). Это метаданные услуги, не догадка по названию (D-08).
            visit_service_doctor_ids = {
                int(row[0])
                for row in (
                    self.db.query(Service.doctor_id)
                    .join(VisitService, VisitService.service_id == Service.id)
                    .filter(
                        VisitService.visit_id == visit.id,
                        Service.queue_tag == queue_tag,
                        Service.doctor_id.isnot(None),
                    )
                    .distinct()
                    .all()
                )
                if row[0] is not None
            }
            if len(visit_service_doctor_ids) == 1:
                candidate_id = next(iter(visit_service_doctor_ids))
                # QD-2E (Codex round-1 P2): единственный кандидат обязан
                # быть пригодным реальным владельцем (активный Doctor +
                # активный User + не внутренний Resource) — стухшая
                # привязка услуги к врачу не строит тихую очередь.
                if eligible_real_doctor(self.db, candidate_id):
                    doctor_id = candidate_id
                    doctor = (
                        self.db.query(Doctor)
                        .filter(Doctor.id == doctor_id)
                        .first()
                    )
                else:
                    logger.error(
                        "QD-2E fail-closed: visit_id=%s queue_tag=%s single "
                        "service doctor_id=%s is not an eligible real owner "
                        "(inactive/unlinked/synthetic) — treating the tag "
                        "as unowned (D-08)",
                        visit.id,
                        queue_tag,
                        candidate_id,
                    )
            elif len(visit_service_doctor_ids) > 1:
                raise owner_configuration_error(
                    queue_tag=queue_tag,
                    detail=(
                        f"visit_id={visit.id} carries multiple explicit "
                        "service doctors for one tag — the operator must "
                        "pick one per booking"
                    ),
                )

        patient = self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
        patient_name = None
        phone = None
        if patient:
            if hasattr(patient, 'short_name'):
                patient_name = patient.short_name()
            elif hasattr(patient, 'last_name') and hasattr(patient, 'first_name'):
                patient_name = f"{patient.last_name} {patient.first_name}".strip()
            phone = patient.phone if hasattr(patient, 'phone') else None

        try:
            existing_claim = lock_and_resolve_active_tag_claim(
                self.db,
                day=target_date,
                queue_tag=queue_tag,
                patient_id=visit.patient_id,
                phone=phone,
                # RQ-25.a.1 (S-22): the legacy-phone bridge is
                # name-narrowed so family members sharing one phone
                # each keep their own claim.
                patient_name=patient_name,
            )
        except QueueClaimConflictError as exc:
            raise MorningAssignmentClaimError(
                "Cannot safely resolve the active queue claim for "
                f"queue_tag={queue_tag}"
            ) from exc

        # An already-open resource queue remains the routing surface for its
        # day after registry deactivation.  The claim coordinator has already
        # locked the exact (day, tag) scope, so this cannot race a competing
        # claim creator in another wizard-family writer.
        if (
            existing_claim is not None
            and existing_claim.daily_queue.queue_resource_id is not None
        ):
            registry_tag = True
            doctor_id = None
            doctor = None

        if existing_claim is not None and doctor_id is not None and not registry_tag:
            claim_queue = existing_claim.daily_queue
            if (
                claim_queue.specialist_id != doctor_id
                or claim_queue.queue_resource_id is not None
            ):
                raise MorningAssignmentClaimError(
                    "Active queue claim belongs to a different owner for "
                    f"queue_tag={queue_tag}"
                )

        surface_reuse = None
        if not doctor_id and not registry_tag:
            # QD-2E surface-reuse ruling (PR review thread 3995689410,
            # P1 — the FINAL business decision): the doctor of a NEW
            # record is NEVER derived from the existence of a queue with
            # the same queue_tag/day. A doctor-owned queue opened for
            # another flow/patient is shared ROUTING metadata, not an
            # owner assignment for THIS unowned visit — borrowing its
            # specialist silently sent the patient to an unrelated
            # doctor (a dentist's queue does not own an unresolved S01
            # visit). The owner comes from the visit/service contract
            # above or from an explicitly configured QueueResource;
            # anything else is the D-08 configuration error below.
            # Multiple doctor queues of one tag are likewise NOT an
            # error by themselves — the per-doctor queue contract (PR-26)
            # keeps them separate and this resolution simply never
            # consults them.
            # The ONE sanctioned reuse of an existing (day, tag) surface
            # is the RESOURCE axis — a queue created by an explicitly
            # configured QueueResource stays the tag's surface even
            # after the registry row is deactivated (the QD-2C
            # deactivation-resilient surface; get_or_create returns it
            # below untouched).
            existing_queue = (
                existing_claim.daily_queue
                if existing_claim is not None
                else (
                    self.db.query(DailyQueue)
                    .filter(
                        DailyQueue.day == target_date,
                        DailyQueue.queue_tag == queue_tag,
                        DailyQueue.active == True,
                    )
                    .first()
                )
            )
            if (
                existing_queue is not None
                and existing_queue.queue_resource_id is not None
            ):
                surface_reuse = existing_queue

        if not doctor_id and not registry_tag and surface_reuse is None:
            # QD-2E (RQ-15.b): fail-closed. Раньше здесь возвращался
            # None (тихая запись без номера — корневая причина QD-0) с
            # general_resource-фолбэком выше; теперь неизвестный
            # владелец = явная конфигурационная ошибка (D-08).
            raise owner_configuration_error(
                queue_tag=queue_tag,
                detail=f"visit_id={visit.id} has no explicit owner surface",
            )

        logger.info(
            f"Используем doctor_id={doctor_id} для queue_tag={queue_tag}, visit_id={visit.id}"
        )

        # ✅ ИСПРАВЛЕНО: Используем SSOT queue_service для получения/создания очереди
        # Получаем информацию о враче для defaults
        defaults = {}
        if doctor:
            defaults = {
                "cabinet_number": doctor.cabinet,
                "max_online_entries": (
                    doctor.max_online_per_day
                    if hasattr(doctor, 'max_online_per_day')
                    else None
                ),
            }

        existing_entry = existing_claim.entry if existing_claim is not None else None
        daily_queue = (
            existing_claim.daily_queue
            if existing_claim is not None
            else surface_reuse
        )

        if not daily_queue:
            daily_queue = queue_service.get_or_create_daily_queue(
                self.db,
                day=target_date,
                specialist_id=doctor_id,
                queue_tag=queue_tag,
                defaults=defaults,
            )

        if existing_entry:
            # QD-2E review P1 (anonymous-claim binding): a reused claim is
            # only a completed assignment when it is LINKED to this
            # registration's patient and visit. The coordinator's phone/name
            # bridge resolves LEGACY rows with patient_id IS NULL (and the
            # patient arm can return a visit-less row) — returning
            # status="existing" for such a row left the ticket anonymous:
            # the wizard activated the visit while the entry kept
            # patient_id/visit_id NULL, and the entry-based start-visit
            # could no longer resolve the visit (the registry gap the
            # review traced through _queue_ops.start_queue_visit and the
            # QR full-update lookup). Mirror the confirmation seam
            # (_reuse_existing_active_entry): bind the missing links
            # atomically in THIS transaction; an INCOMPATIBLE existing
            # binding is a hard conflict and is never silently rebound.
            # The number, queue_time and the rest of the original ticket
            # stay untouched.
            if existing_entry.patient_id not in (None, visit.patient_id):
                # The coordinator already rejects cross-patient claims
                # (patient arm is exact, the post-check folds the rest) —
                # this guard is the belt-and-suspenders boundary contract.
                raise MorningAssignmentClaimError(
                    "Active queue claim is already bound to another "
                    f"patient for queue_tag={queue_tag}"
                )
            if existing_entry.visit_id not in (None, visit.id):
                raise MorningAssignmentClaimError(
                    "Active queue claim is already bound to another "
                    f"visit for queue_tag={queue_tag}"
                )
            if existing_entry.patient_id is None:
                existing_entry.patient_id = visit.patient_id
            if existing_entry.visit_id is None:
                existing_entry.visit_id = visit.id
            logger.info(
                "Active queue entry already exists for queue %s",
                queue_tag,
            )
            return MorningAssignmentPreparedQueueAssignment(
                assignment={
                    "queue_tag": queue_tag,
                    "queue_id": daily_queue.id,
                    "number": existing_entry.number,
                    "status": "existing",
                }
            )
        # Получаем queue_time (бизнес-время регистрации)
        from zoneinfo import ZoneInfo

        from app.crud.clinic import get_queue_settings

        queue_settings = get_queue_settings(self.db)
        timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        queue_time = datetime.now(timezone)

        # ⭐ ИСПРАВЛЕНО: Получаем услуги визита для данного queue_tag
        visit_services = (
            self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        # Фильтруем услуги по queue_tag и формируем services/service_codes
        services_for_entry = []
        service_codes_for_entry = []

        for vs in visit_services:
            service = self.db.query(Service).filter(Service.id == vs.service_id).first()
            if service and service.queue_tag == queue_tag:
                code = service.service_code or get_service_code(service.id, self.db)
                if code:
                    service_codes_for_entry.append(code.upper() if code else None)
                    services_for_entry.append(
                        {
                            "id": service.id,
                            "code": code.upper() if code else None,
                            "name": service.name,
                            "price": float(vs.price) if vs.price else 0,
                        }
                    )

        # Если не нашли услуги с matching queue_tag, добавляем все услуги визита
        if not services_for_entry:
            for vs in visit_services:
                service = (
                    self.db.query(Service).filter(Service.id == vs.service_id).first()
                )
                if service:
                    code = service.service_code or get_service_code(service.id, self.db)
                    if code:
                        service_codes_for_entry.append(code.upper() if code else None)
                        services_for_entry.append(
                            {
                                "id": service.id,
                                "code": code.upper() if code else None,
                                "name": service.name,
                                "price": float(vs.price) if vs.price else 0,
                            }
                        )

        # ✅ ИСПРАВЛЕНО: Используем SSOT метод для создания записи С услугами
        return MorningAssignmentPreparedQueueAssignment(
            create_handoff=MorningAssignmentCreateBranchHandoff(
                queue_tag=queue_tag,
                daily_queue=daily_queue,
                create_entry_kwargs={
                    "daily_queue": daily_queue,
                    "patient_id": visit.patient_id,
                    "patient_name": patient_name,
                    "phone": phone,
                    "visit_id": visit.id,
                    "source": source,
                    "status": "waiting",
                    "queue_time": queue_time,
                    "services": services_for_entry,
                    "service_codes": service_codes_for_entry,
                    "auto_number": True,
                    "commit": False,
                },
            )
        )

    def get_morning_assignment_stats(
        self, target_date: date | None = None
    ) -> dict[str, any]:
        """Получает статистику утренней сборки"""
        if not target_date:
            target_date = _clinic_today(self.db)

        # Подтвержденные визиты на дату
        confirmed_visits = (
            self.db.query(Visit)
            .filter(
                and_(
                    Visit.visit_date == target_date,
                    Visit.status.in_(["confirmed", "open"]),
                    Visit.confirmed_at.isnot(None),
                )
            )
            .count()
        )

        # Визиты со статусом "open" (уже обработанные)
        processed_visits = (
            self.db.query(Visit)
            .filter(and_(Visit.visit_date == target_date, Visit.status == "open"))
            .count()
        )

        # Записи в очередях на дату
        queue_entries = (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue)
            .filter(DailyQueue.day == target_date)
            .count()
        )

        return {
            "date": target_date.isoformat(),
            "confirmed_visits": confirmed_visits,
            "processed_visits": processed_visits,
            "queue_entries": queue_entries,
            "pending_processing": confirmed_visits - processed_visits,
        }


# Глобальная функция для запуска утренней сборки
def run_morning_assignment(target_date: date | None = None) -> dict[str, any]:
    """
    Запускает утреннюю сборку для присвоения номеров в очередях
    Может быть вызвана из cron job или API эндпоинта
    """
    with MorningAssignmentService() as service:
        return service.run_morning_assignment(target_date)


def get_assignment_stats(target_date: date | None = None) -> dict[str, any]:
    """Получает статистику утренней сборки"""
    with MorningAssignmentService() as service:
        return service.get_morning_assignment_stats(target_date)


# Функция для тестирования
def test_morning_assignment():
    """Тестовая функция для проверки утренней сборки"""
    logger.info("🧪 Запуск тестирования утренней сборки")

    result = run_morning_assignment()
    stats = get_assignment_stats()

    logger.info(
        "Результат утренней сборки: Успех=%s, Обработано визитов=%d, Присвоено номеров=%d, Ошибки=%d",
        result['success'],
        result['processed_visits'],
        result['assigned_queues'],
        len(result['errors']),
    )
    logger.info(
        "Статистика: Подтвержденные визиты=%d, Обработанные визиты=%d, Записи в очередях=%d, Ожидают обработки=%d",
        stats['confirmed_visits'],
        stats['processed_visits'],
        stats['queue_entries'],
        stats['pending_processing'],
    )

    return result, stats


if __name__ == "__main__":
    # Запуск тестирования при прямом вызове
    test_morning_assignment()
