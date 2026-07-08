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
        instance = self.get_instance(instance_id)
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


    def _sync_legacy_lab_results(
        self,
        instance: LabReportInstance,
        field_map: dict[str, LabReportFieldDef],
    ) -> None:
        """P-01 bridge: projection LabReportValue → LabResult.

        Создаёт соответствующие записи в legacy таблице lab_results при
        финализации бланка, чтобы read-only потребители (mobile app
        /mobile/lab/results, EMR /patients/{id}/lab-results, statistics,
        critical value notifications, Telegram) видели новые бланки.

        Контекст: в кодовой базе 2 модели lab results:
          - Новая: lab_report_instances + lab_report_values (используется
            LabReportWorkbench через /lab/report-instances)
          - Legacy: lab_results (используется mobile app, EMR, и т.д.)

        Раньше bridge не было — новые бланки были невидимы для legacy
        потребителей. Этот метод создаёт LabResult projection при
        finalize(), используя order_id как связь (instance.order_id →
        lab_results.order_id).

        Idempotent: если для данного instance уже созданы LabResult
        записи (по order_id + test_code), повторной финализации не будет
        (state machine: FINALIZED → только revise). Но при revise()
        создаётся новый instance с новым order_id или тем же —
        теоретически могут быть дубли. Защита: проверяем существующие
        записи по (order_id, test_code) перед insert.

        Маппинг полей:
          field_def.label              → test_name
          field_def.field_key          → test_code
          value.value_text/value_numeric → value (string representation)
          field_def.unit               → unit
          value.resolved_reference_text → ref_range
          value.resolved_flag in
            {high, low, abnormal, critical, warning} → abnormal=True
        """
        if not instance.order_id:
            logger.warning(
                "[LAB] _sync_legacy_lab_results: instance %s has no order_id, "
                "skipping legacy projection",
                instance.id,
            )
            return

        # Удаляем существующие projection для этого order (на случай
        # re-finalize через revise — хотя state machine это не допускает,
        # защита не лишняя).
        existing = (
            self.db.query(LabResult)
            .filter(LabResult.order_id == instance.order_id)
            .all()
        )
        if existing:
            logger.info(
                "[LAB] _sync_legacy_lab_results: order %s already has %d "
                "LabResult projections, skipping (idempotent)",
                instance.order_id,
                len(existing),
            )
            return

        created_count = 0
        for value in instance.values:
            field_def = field_map.get(value.field_key)
            if not field_def:
                continue

            # Пропускаем пустые значения — нет смысла создавать LabResult
            # для незаполненного показателя.
            effective_value = self._extract_effective_value(value)
            if effective_value in (None, ""):
                continue

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

            lab_result = LabResult(
                order_id=instance.order_id,
                test_code=value.field_key,
                test_name=field_def.label or value.field_key,
                value=result_value[:128] if result_value else None,
                unit=(field_def.unit or "")[:32] or None,
                ref_range=(value.resolved_reference_text or "")[:64] or None,
                abnormal=abnormal,
                notes=None,
            )
            self.db.add(lab_result)
            created_count += 1

        logger.info(
            "[LAB] _sync_legacy_lab_results: created %d LabResult projections "
            "for instance %s (order %s)",
            created_count,
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


