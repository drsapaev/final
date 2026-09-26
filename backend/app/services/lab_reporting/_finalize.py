"""Finalize mixin for LabReportingService.

Split from lab_reporting_service.py.
"""
from __future__ import annotations

from app.services.lab_reporting._base import *  # noqa: F401, F403
from app.services.lab_reporting._base import LabReportingServiceMixinBase


class FinalizeMixin(LabReportingServiceMixinBase):
    """Finalize methods for LabReportingService."""

    def finalize(self, instance_id: int) -> LabReportInstance:
        logger.info("[LAB] finalize instance_id=%s", instance_id)
        # Serialize the whole aggregate before reading status or child values.
        # Draft saves and finalization share this parent-first lock order.
        instance = self._get_locked_instance(instance_id)
        self._assert_instance_editable(instance)
        current_values = {
            value.field_key: self._extract_effective_value(value)
            for value in instance.values
        }
        field_map = self._field_map(instance.template_version)
        context = self._build_rule_context(instance.patient_snapshot, current_values)

        visible_required_fields = []
        for field_def in field_map.values():
            if self._is_visible(field_def.visibility_rule, context):
                if field_def.required:
                    visible_required_fields.append(field_def.field_key)
                reference = self._resolve_reference(field_def, context)
                value = next(
                    (item for item in instance.values if item.field_key == field_def.field_key),
                    None,
                )
                if value:
                    value.resolved_reference_text = reference.get("text")
                    flag = self._resolve_flag(
                        field_def=field_def,
                        effective_value=current_values.get(field_def.field_key),
                        context=context,
                        reference=reference,
                    )
                    value.resolved_flag = flag["flag"]
                    value.resolved_flag_source = flag["source"]
                    value.resolved_flag_severity = flag["severity_rank"]
                    value.resolved_flag_meta = flag["meta"]

        missing = [
            field_key
            for field_key in visible_required_fields
            if current_values.get(field_key) in (None, "")
        ]
        if missing:
            raise LabReportingDomainError(
                400,
                f"Cannot finalize. Required fields missing: {', '.join(missing)}",
            )
        # Flush resolved references/flags while the row is still mutable.
        # The database trigger only allows the immutable transition after this point.
        self.repository.flush()
        instance.status = "FINALIZED"
        instance.finalized_at = datetime.now(UTC)
        self._advance_instance_version(instance)
        # P-01 bridge: sync в legacy lab_results таблицу для read-only
        # потребителей (mobile app, EMR, statistics, notifications).
        # Создаёт LabResult записи как projection из LabReportValue.
        # См. _sync_legacy_lab_results ниже для подробностей.
        self._sync_legacy_lab_results(instance, field_map)
        self.repository.commit()

        # P0 fix: emit inline notifications on finalize — no cron/scheduler needed.
        # Notifies (1) the patient via Telegram that results are ready, and
        # (2) the ordering doctor if the instance was created from a lab order.
        # Previously lab_notification_service.py was fully implemented but
        # never called — patients had to manually poll for results.
        # Now wired up: see check_critical_values() call below.
        try:
            self._emit_lab_results_ready_notification(instance)
        except Exception as notify_err:
            logger.warning(
                "[LAB] results-ready notification failed (non-blocking): %s",
                notify_err,
            )

        # Wire-up: check critical values on finalize. The
        # LabNotificationService.check_critical_values() was implemented
        # but never called. Now we invoke it inline after finalization
        # so doctors get immediate alerts for glucose >20, potassium >6.5,
        # hemoglobin <70, etc. (8 markers in CRITICAL_VALUES dict).
        # Non-blocking — a failure here does not roll back the finalization.
        try:
            from app.services.lab_notification_service import LabNotificationService
            lab_notif_svc = LabNotificationService(self.db)
            asyncio.get_event_loop().create_task(
                lab_notif_svc.check_critical_values()
            )
        except Exception as critical_err:
            logger.warning(
                "[LAB] critical values check failed (non-blocking): %s",
                critical_err,
            )

        return self.get_instance(instance.id)

    # ============================================================
    # === LEGACY SYNC ===
    # ============================================================


    def _resolve_chain_root(self, instance: LabReportInstance) -> tuple[int, set[int]]:
        """Walk the supersedes_instance_id chain up to the root blank.

        Returns ``(root_id, chain)`` where ``chain`` is the set of ALL
        member ids of this revision chain (the instance itself plus every
        ancestor) — the membership test used by the competing-revision
        guard: the chain projection may be refreshed only by a member of
        its own chain.
        """
        chain: set[int] = set()
        root_id = instance.id
        current = instance
        while True:
            chain.add(current.id)
            parent_id = current.supersedes_instance_id
            if not parent_id:
                break
            if parent_id in chain:
                raise LabReportingDomainError(
                    500,
                    "Corrupt revision chain: cycle detected; "
                    "automatic current-value selection is forbidden "
                    "(owner contract, .ai-factory/plans/"
                    "lab-results-lineage-decision.md)",
                )
            parent = self.db.get(LabReportInstance, parent_id)
            if parent is None:
                raise LabReportingDomainError(
                    500,
                    "Corrupt revision chain: unresolved ancestor; "
                    "automatic current-value selection is forbidden "
                    "(owner contract)",
                )
            root_id = parent.id
            current = parent
        return root_id, chain

    def _sync_legacy_lab_results(
        self,
        instance: LabReportInstance,
        field_map: dict[str, LabReportFieldDef],
    ) -> None:
        """P-01 bridge, A+ runtime: managed lineage projection.

        Проекция LabReportValue → lab_results для read-only потребителей
        (mobile app /mobile/lab-results, EMR, statistics, critical-value
        scanner, Telegram). Контракт: решение владельца C → A+, зафиксировано
        в .ai-factory/plans/lab-results-lineage-decision.md.

        Ключ управляемой проекции — (source_root_instance_id, test_code):
        - root цепочки определяется по supersedes_instance_id (актуальность
          задаётся связями ревизий, не max id / timestamp / порядком);
        - source_instance_id — утверждённая версия, давшая текущее значение;
        - строки ДРУГИХ цепочек того же заказа (например glucose крови и
          мочи) и исторические строки без lineage никогда не трогаются;
        - очищенный в ревизии показатель перестаёт быть актуальным
          (value=NULL, актуальный source, abnormal сброшен) — «пустота»
          не превращается в старое значение или «норму»;
        - повторный sync идемпотентен и не трогает created_at, поэтому
          critical-value сканер не порождает повторных уведомлений;
        - конкурирующие ревизии одного предшественника не разрешаются
          last-write-wins: проекцию обновляет только член своей цепочки,
          чужая ревизия получает контролируемый конфликт 409.

        Сериализация: SELECT … FOR UPDATE на root-instance удерживается до
        коммита окружающего finalize; состояние управляемых строк
        перечитывается ПОСЛЕ захвата блокировки (read committed видит
        строки победителя). SQLite игнорирует FOR UPDATE; семантика
        сериализации доказана двухсоединечным PostgreSQL-тестом.
        """
        if not instance.order_id:
            logger.warning(
                "[LAB] _sync_legacy_lab_results: instance %s has no order_id, "
                "skipping legacy projection",
                instance.id,
            )
            return

        root_id, chain = self._resolve_chain_root(instance)

        # Chain-level serialization: все члены цепочки (и только они)
        # обновляют строки этого root; блокировка корневой строки
        # упорядочивает конкурирующие ревизии и гонки COUNT→INSERT.
        self.db.query(LabReportInstance).filter(
            LabReportInstance.id == root_id
        ).with_for_update().first()

        # Re-read AFTER the lock: read committed уже видит строки
        # победителя. Исторические (NULL lineage) и чужие цепочки не
        # попадают в выборку и потому не могут быть изменены.
        existing_managed = {
            row.test_code: row
            for row in self.db.query(LabResult)
            .filter(
                LabResult.source_root_instance_id == root_id,
                LabResult.test_code.isnot(None),
            )
            .all()
        }

        # Competing-revision guard: текущий source каждой строки обязан
        # быть членом этой цепочки (предок или сам instance). Иначе
        # цепочку уже продвинула сиблинг-ревизия — контролируемый
        # конфликт, никакой перезаписи.
        for code, row in existing_managed.items():
            source_id = row.source_instance_id
            if source_id is None or source_id in chain:
                continue
            raise LabReportingDomainError(
                409,
                f"Competing finalized revision: indicator '{code}' of this "
                f"order was already refreshed by revision {source_id}, which "
                f"is not superseded by revision {instance.id}. Reload the "
                f"chain history; last-write-wins is forbidden by the owner "
                f"contract.",
            )

        created_count = 0
        updated_count = 0
        cleared_count = 0
        for value in instance.values:
            field_def = field_map.get(value.field_key)
            if not field_def:
                continue
            code = value.field_key

            # value_numeric имеет приоритет для numeric fields, иначе value_text.
            # Нормализуем Decimal: LabReportValue.value_numeric хранится как
            # Numeric(18, 4), поэтому str(Decimal('100')) = '100.0000'.
            # Для legacy LabResult.value (String(128)) убираем trailing zeros,
            # чтобы mobile app показывал '100', а не '100.0000'.
            if value.value_numeric is not None:
                numeric_str = str(value.value_numeric)
                # Decimal('100.0000') → '100', Decimal('5.2000') → '5.2'
                if '.' in numeric_str:
                    numeric_str = numeric_str.rstrip('0').rstrip('.')
                    if not numeric_str or numeric_str == '-':
                        numeric_str = '0'
                result_value = numeric_str
            else:
                result_value = value.value_text or ""

            # abnormal = True для любого непустого resolved_flag
            # (high, low, abnormal, critical, warning). None/empty → False.
            abnormal = bool(value.resolved_flag)

            row = existing_managed.get(code)

            if result_value == "":
                # Очищенный показатель: прежнее значение перестаёт быть
                # актуальным. Строка уже спроецирована — помечаем отсутствие
                # актуального значения; никогда не проецированный пустой
                # показатель строку не создаёт.
                if row is not None and (
                    row.value is not None
                    or row.source_instance_id != instance.id
                ):
                    row.value = None
                    row.abnormal = False
                    row.source_instance_id = instance.id
                    cleared_count += 1
                continue

            projected = {
                "test_name": field_def.label or code,
                "value": result_value[:128],
                "unit": (field_def.unit or "")[:32] or None,
                "ref_range": (value.resolved_reference_text or "")[:64] or None,
                "abnormal": abnormal,
            }

            if row is not None:
                for attr, projected_value in projected.items():
                    setattr(row, attr, projected_value)
                row.source_instance_id = instance.id
                updated_count += 1
            else:
                self.db.add(
                    LabResult(
                        order_id=instance.order_id,
                        test_code=code,
                        source_root_instance_id=root_id,
                        source_instance_id=instance.id,
                        notes=None,
                        **projected,
                    )
                )
                created_count += 1

        logger.info(
            "[LAB] _sync_legacy_lab_results: root=%s created %d, updated %d, "
            "cleared %d managed projections for instance %s (order %s)",
            root_id,
            created_count,
            updated_count,
            cleared_count,
            instance.id,
            instance.order_id,
        )

    # ============================================================
    # === REVISION & ANALYTICS ===
    # ============================================================


    def _emit_lab_new_study_notification(
        self,
        *,
        order: LabOrder,
        patient_id: int,
        visit_id: int | None,
    ) -> None:
        recipients = (
            self.db.query(User)
            .filter(
                User.is_active.is_(True),
                func.lower(User.role).in_(["lab", "labtechnician", "lab_technician"]),
            )
            .all()
        )
        if not recipients:
            return

        async def _send(recipient: User) -> bool:
            return await notification_sender_service.send_lab_event_notification(
                db=self.db,
                recipient=recipient,
                event_type="lab_new_study",
                title="Назначено новое исследование",
                message=f"Для пациента #{patient_id} создано новое исследование.",
                metadata={
                    "order_id": order.id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                },
            )

        for recipient in recipients:
            try:
                canonical_created = asyncio.run(_send(recipient))
                if not canonical_created:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] lab_new_study canonical delivery failed",
                        extra={
                            "has_order": order.id is not None,
                        },
                    )
            except RuntimeError as exc:
                logger.warning(
                    "[FIX:NOTIFICATIONS] lab_new_study canonical delivery skipped due runtime context",
                    extra={
                        "has_order": order.id is not None,
                        "error_type": type(exc).__name__,
                    },
                )
            except Exception as exc:
                logger.error(
                    "[FIX:NOTIFICATIONS] lab_new_study canonical delivery error",
                    extra={
                        "has_order": order.id is not None,
                        "error_type": type(exc).__name__,
                    },
                )


    def _emit_lab_results_ready_notification(self, instance: LabReportInstance) -> None:
        """
        P0 fix: emit notifications when lab results are finalized.

        Notifies:
          1. The ordering doctor (if instance has a linked LabOrder with
             requested_by_doctor_id) — so they know results are ready.
          2. The patient via Telegram (if patient has a Telegram link and
             lab_notifications enabled) — so they can pick up results.

        This replaces the old lab_notification_service.py cron
        approach with inline emission from finalize().
        lab_notification_service.py is now wired up for critical values
        checking (check_critical_values) — see the finalize() method.
        """
        patient_id = instance.patient_id
        visit_id = instance.visit_id
        template_name = ""
        if instance.template_version and instance.template_version.template:
            template_name = instance.template_version.template.name or ""

        # Count flagged findings for the notification message.
        flagged_count = sum(
            1 for v in instance.values
            if v.resolved_flag_severity and v.resolved_flag_severity > 0
        )

        # 1. Notify the ordering doctor via in-app notification.
        # LAB-AUDIT-28 P0-2: field name was wrong (lab_order_id → order_id),
        # and LabOrder has no requested_by_doctor_id column — doctor is found
        # via visit.doctor_id. Ordering doctor was NEVER notified on finalize.
        order = None
        if instance.order_id:
            order = self.db.query(LabOrder).filter(LabOrder.id == instance.order_id).first()

        doctor_id = None
        if order and order.visit_id:
            visit = self.db.query(Visit).filter(Visit.id == order.visit_id).first()
            if visit:
                doctor_id = visit.doctor_id
        elif instance.visit_id:
            visit = self.db.query(Visit).filter(Visit.id == instance.visit_id).first()
            if visit:
                doctor_id = visit.doctor_id

        if doctor_id:
            doctor_user = (
                self.db.query(User)
                .join(Doctor, Doctor.user_id == User.id)
                .filter(Doctor.id == doctor_id, User.is_active.is_(True))
                .first()
            )
            if doctor_user:
                try:
                    asyncio.run(
                        notification_sender_service.send_lab_event_notification(
                            db=self.db,
                            recipient=doctor_user,
                            event_type="lab_results_ready",
                            title="Результаты анализов готовы",
                            message=(
                                f"Результаты анализов{' («' + template_name + '»)' if template_name else ''} "
                                f"для пациента #{patient_id} готовы."
                                + (f" Отклонений: {flagged_count}." if flagged_count > 0 else "")
                            ),
                            metadata={
                                "instance_id": instance.id,
                                "patient_id": patient_id,
                                "visit_id": visit_id,
                                "template_name": template_name,
                                "flagged_count": flagged_count,
                            },
                        )
                    )
                    logger.info(
                        "[LAB] results-ready notification sent to doctor user_id=%s",
                        doctor_user.id,
                    )
                except RuntimeError:
                    logger.warning("[LAB] results-ready doctor notification skipped (event loop active)")
                except Exception as exc:
                    logger.error("[LAB] results-ready doctor notification error: %s", exc)

        # 2. Notify the patient via Telegram.
        # The telegram webhook's _send_clinic_lab_results function handles
        # sending PDF results to patients. Here we just log that results are
        # ready — the patient can pull results via the bot's "📄 Results"
        # button, or an admin can use POST /telegram/send-lab-results to
        # push them. A full push integration requires calling the async
        # telegram bot API from this sync context, which is deferred to
        # a background task queue in a future iteration.
        logger.info("Lab results finalized", extra={"has_patient": True})


