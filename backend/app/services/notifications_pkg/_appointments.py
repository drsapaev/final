"""Appointments mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    NotificationSenderMixinBase,
    Session,
    datetime,
    logger,
)


class AppointmentsMixin(NotificationSenderMixinBase):
    """Appointments methods for NotificationSenderService."""

    async def send_appointment_reminder(
        self,
        patient_email: str,
        patient_phone: str,
        appointment_date: datetime,
        doctor_name: str,
        department: str,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка напоминания о записи"""
        subject = "Напоминание о записи к врачу"

        # Формируем сообщения
        email_body = f"""
        Здравствуйте!

        Напоминаем о записи к врачу {doctor_name} в отделении {department}.
        Дата и время: {appointment_date.strftime('%d.%m.%Y в %H:%M')}

        Пожалуйста, не забудьте взять с собой документы и прийти за 10 минут до приёма.

        С уважением,
        Администрация клиники
        """

        sms_message = f"Напоминание: запись к {doctor_name} {appointment_date.strftime('%d.%m в %H:%M')}"

        telegram_message = f"""
        📅 <b>Напоминание о записи</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {appointment_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Запись к {doctor_name} {appointment_date.strftime('%d.%m.%Y в %H:%M')}",
                    data={
                        "type": "appointment_reminder",
                        "appointment_date": appointment_date.isoformat(),
                        "doctor_name": doctor_name,
                        "department": department,
                    },
                    db=db,
                )

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        if db and patient_id:
            results["telegram"] = await self.send_patient_telegram_event_notification(
                db=db,
                patient_id=patient_id,
                event_type="appointment_reminder",
                metadata={
                    "appointment_date": appointment_date.strftime("%d.%m.%Y %H:%M"),
                    "doctor_name": doctor_name,
                    "department": department,
                },
            )
        else:
            results["telegram"] = await self.send_telegram(telegram_message)

        return results


    async def send_visit_confirmation(
        self,
        patient_email: str,
        patient_phone: str,
        visit_date: datetime,
        doctor_name: str,
        department: str,
        queue_number: int | None = None,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка подтверждения визита"""
        subject = "Подтверждение визита к врачу"

        email_body = f"""
        Здравствуйте!

        Ваш визит к врачу {doctor_name} в отделении {department} подтверждён.
        Дата и время: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            email_body += f"Номер в очереди: {queue_number}\n"

        email_body += """
        Пожалуйста, придите за 10 минут до назначенного времени.

        С уважением,
        Администрация клиники
        """

        sms_message = (
            f"Визит к {doctor_name} подтверждён {visit_date.strftime('%d.%m в %H:%M')}"
        )
        if queue_number:
            sms_message += f", очередь №{queue_number}"

        telegram_message = f"""
        ✅ <b>Подтверждение визита</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            telegram_message += f"🎫 Номер в очереди: {queue_number}"

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Ваш визит к {doctor_name} подтверждён на {visit_date.strftime('%d.%m.%Y в %H:%M')}",
                    data={
                        "type": "visit_confirmation",
                        "visit_date": visit_date.isoformat(),
                        "doctor_name": doctor_name,
                        "department": department,
                        "queue_number": queue_number,
                    },
                    db=db,
                )

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results


    async def send_appointment_confirmation(
        self,
        db: Session,
        appointment_id: int,
    ) -> dict[str, bool]:
        """Отправка подтверждения записи (Unified: Push, Email, SMS, Telegram)"""
        from app.models.appointment import Appointment
        from app.models.user import User

        try:
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return {}

            doctor_name = appointment.doctor.name if appointment.doctor else "Врач"
            specialty = appointment.doctor.specialty if appointment.doctor else ""
            visit_date_str = appointment.appointment_date.strftime('%d.%m.%Y в %H:%M')
            appointment_datetime = appointment.appointment_date
            if appointment.appointment_time:
                try:
                    appointment_datetime = datetime.combine(
                        appointment.appointment_date,
                        datetime.strptime(appointment.appointment_time, "%H:%M").time(),
                    )
                except ValueError:
                    logger.warning(
                        "Failed to parse appointment time for notification",
                        extra={
                            "has_appointment_time": True,
                        },
                    )

            # --- Push Notification Logic ---
            if appointment.patient and appointment.patient.user_id:
                user = db.query(User).filter(User.id == appointment.patient.user_id).first()
                if user:
                    title = "Запись подтверждена"
                    message = f"Ваша запись к врачу {doctor_name} на {visit_date_str} подтверждена"

                    await self.send_push(
                        user_id=user.id,
                        title=title,
                        message=message,
                        data={
                            "type": "appointment_confirmation",
                            "appointment_id": appointment_id,
                        },
                        db=db
                    )

            # --- Unified Channels Logic ---
            # Call the lower-level send_visit_confirmation for Email/SMS/Telegram
            # We need patient email/phone.
            patient_email = appointment.patient.email if appointment.patient else None
            patient_phone = appointment.patient.phone if appointment.patient else None

            # Use send_visit_confirmation which handles Email/SMS/Telegram template formatting
            # Note: send_visit_confirmation sends "confirmation" logic.
            # Ideally we reuse it.

            return await self.send_visit_confirmation(
                patient_email=patient_email,
                patient_phone=patient_phone,
                visit_date=appointment_datetime,
                doctor_name=doctor_name,
                department=appointment.department or specialty,
                db=db,
                patient_id=appointment.patient_id,
            )

        except Exception as e:
            logger.error(f"Error sending appointment confirmation: {e}")
            return {}


    async def send_queue_update(
        self,
        department: str,
        current_number: int,
        estimated_wait: str,
        patient_id: int | None = None,
        db: Session | None = None,
    ) -> bool:
        """Отправка обновления очереди (Telegram + Push)"""
        message = (
            f"📊 Обновление очереди\n\n"
            f"Отделение: {department}\n"
            f"Текущий номер: {current_number}\n"
            f"Примерное время ожидания: {estimated_wait}\n"
            f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )

        if db:
            platform_service = self._platform_service(db)
            if patient_id:
                from app.models.patient import Patient

                patient = db.query(Patient).filter(Patient.id == patient_id).first()
                if patient and patient.user_id:
                    await self.send_push(
                        user_id=patient.user_id,
                        title="Обновление очереди",
                        message=f"Ваша очередь обновлена: #{current_number}",
                        data={
                            "type": "queue_update",
                            "department": department,
                            "current_number": current_number,
                            "estimated_wait": estimated_wait,
                        },
                        db=db,
                    )
            else:
                targets = platform_service.resolve_users_for_department(department)
                await platform_service.record_delivery_for_users(
                    users=targets,
                    event_type="queue_update",
                    title="Обновление очереди",
                    message=message,
                    source_module="queue",
                    recipient_type="user",
                    severity="info",
                    priority="normal",
                    payload_snapshot={
                        "department": department,
                        "current_number": current_number,
                        "estimated_wait": estimated_wait,
                    },
                    transport_type="queue_update",
                )

        return await self.send_telegram(message)


    async def send_patient_queue_update(
        self,
        db: Session,
        patient_id: int,
        queue_position: int,
        specialty: str
    ) -> bool:
        """Отправка уведомления пациенту о позиции в очереди (Mobile/Push)"""
        try:
             # Находим пользователя через пациента
             from app.models.patient import Patient
             from app.models.user import User

             patient = db.query(Patient).filter(Patient.id == patient_id).first()
             if not patient or not patient.user_id:
                 return False

             user = db.query(User).filter(User.id == patient.user_id).first()
             if not user:
                 return False

             title = "Обновление очереди"
             message = f"Ваша позиция в очереди к {specialty}: #{queue_position}"

             # Push
             if user:
                  await self.send_push(
                      user_id=user.id,
                      title=title,
                     message=message,
                     data={
                         "type": "queue_update",
                         "queue_position": queue_position,
                         "specialty": specialty,
                     },
                     db=db
                 )

             # Telegram (если есть)
             if user.telegram_id:
                 await self.send_telegram_message(
                     user.telegram_id,
                     f"🔢 <b>{title}</b>\n\n{message}"
                 )

             return True
        except Exception as e:
            logger.error(f"Error sending patient queue update: {e}")
            return False


