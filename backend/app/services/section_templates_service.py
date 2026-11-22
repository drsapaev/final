"""
DoctorSectionTemplatesService - Универсальный сервис для персональных шаблонов

Клиническая память врача по секциям EMR:
- Обучение при подписании EMR
- Получение шаблонов по секции + диагнозу
- Pin/Unpin
- Edit (replace / save_as_new)
- Delete

Key features:
- icd10_code nullable: сначала ищем по диагнозу, потом общие
- usage_count для частотного ранжирования
- is_stale для предупреждения о неиспользуемых
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from ..models.section_templates import (
    DoctorSectionTemplate,
    DoctorSectionTemplateResponse,
    DoctorSectionTemplatesListResponse,
    SectionType,
)

logger = logging.getLogger(__name__)

# Constants
MAX_PINNED_PER_SECTION = 3
STALE_MONTHS = 12
FREQUENCY_THRESHOLD_HIGH = 5
FREQUENCY_THRESHOLD_LOW = 2


class DoctorSectionTemplatesService:
    """
    Универсальный сервис для работы с персональными шаблонами врача.
    """

    def __init__(self, db: Session):
        self.db = db

    def learn_from_signed_emr(
        self,
        doctor_id: int,
        section_type: str,
        text: str,
        icd10_code: str | None = None,
    ) -> DoctorSectionTemplate | None:
        """
        Обучение на подписанном EMR.

        Вызывается при подписании EMR для каждой секции с непустым текстом.

        Args:
            doctor_id: ID врача
            section_type: Тип секции (complaints, anamnesis, etc.)
            text: Текст секции
            icd10_code: Код МКБ-10 (опционально)

        Returns:
            Созданный или обновленный шаблон
        """
        if not text or not text.strip():
            return None

        # Validate section_type
        try:
            SectionType(section_type)
        except ValueError:
            logger.warning(f"Invalid section_type: {section_type}")
            return None

        # Normalize and hash
        _normalized = DoctorSectionTemplate.normalize_text(text)
        template_hash = DoctorSectionTemplate.compute_hash(text)

        try:
            # Check if template already exists
            stmt = select(DoctorSectionTemplate).where(
                and_(
                    DoctorSectionTemplate.doctor_id == doctor_id,
                    DoctorSectionTemplate.section_type == section_type,
                    DoctorSectionTemplate.template_hash == template_hash,
                )
            )
            result = self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update usage count and last_used_at
                existing.usage_count += 1
                existing.last_used_at = datetime.now(UTC)
                # Update icd10_code if provided and different
                if icd10_code and not existing.icd10_code:
                    existing.icd10_code = icd10_code.upper()
                self.db.commit()
                self.db.refresh(existing)
                logger.info(f"Updated template {existing.id} usage_count={existing.usage_count}")
                return existing
            else:
                # Create new template
                new_template = DoctorSectionTemplate(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor_id,
                    section_type=section_type,
                    icd10_code=icd10_code.upper() if icd10_code else None,
                    template_text=text.strip(),
                    template_hash=template_hash,
                    usage_count=1,
                    is_pinned=False,
                    last_used_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                )
                self.db.add(new_template)
                self.db.commit()
                self.db.refresh(new_template)
                logger.info(f"Created new template {new_template.id} for {section_type}")
                return new_template

        except Exception as e:
            logger.error(f"Error in learn_from_signed_emr: {e}")
            self.db.rollback()
            return None

    def get_templates(
        self,
        doctor_id: int,
        section_type: str,
        icd10_code: str | None = None,
        limit: int = 10,
    ) -> DoctorSectionTemplatesListResponse:
        """
        Получить шаблоны врача по секции и диагнозу.

        Стратегия поиска:
        1. Сначала по конкретному icd10_code (если указан)
        2. Затем общие (icd10_code IS NULL)

        Сортировка:
        1. Закреплённые (is_pinned DESC)
        2. Частота использования (usage_count DESC)
        3. Последнее использование (last_used_at DESC)

        Args:
            doctor_id: ID врача
            section_type: Тип секции
            icd10_code: Код МКБ-10 (опционально)
            limit: Максимум шаблонов

        Returns:
            Список шаблонов с метаданными
        """
        # Validate section_type
        try:
            SectionType(section_type)
        except ValueError:
            return DoctorSectionTemplatesListResponse(
                section_type=section_type,
                icd10_code=icd10_code,
                templates=[],
                total=0,
            )

        # Build query - get both specific and general templates
        if icd10_code:
            icd10_upper = icd10_code.upper()
            stmt = (
                select(DoctorSectionTemplate)
                .where(
                    and_(
                        DoctorSectionTemplate.doctor_id == doctor_id,
                        DoctorSectionTemplate.section_type == section_type,
                        or_(
                            DoctorSectionTemplate.icd10_code == icd10_upper,
                            DoctorSectionTemplate.icd10_code.is_(None),
                        ),
                    )
                )
                .order_by(
                    DoctorSectionTemplate.is_pinned.desc(),
                    DoctorSectionTemplate.usage_count.desc(),
                    DoctorSectionTemplate.last_used_at.desc(),
                )
                .limit(limit)
            )
        else:
            # Only general templates
            stmt = (
                select(DoctorSectionTemplate)
                .where(
                    and_(
                        DoctorSectionTemplate.doctor_id == doctor_id,
                        DoctorSectionTemplate.section_type == section_type,
                    )
                )
                .order_by(
                    DoctorSectionTemplate.is_pinned.desc(),
                    DoctorSectionTemplate.usage_count.desc(),
                    DoctorSectionTemplate.last_used_at.desc(),
                )
                .limit(limit)
            )

        result = self.db.execute(stmt)
        templates = result.scalars().all()

        # Helper functions
        def get_frequency_label(usage: int) -> str | None:
            if usage >= FREQUENCY_THRESHOLD_HIGH:
                return "часто"
            elif usage <= FREQUENCY_THRESHOLD_LOW:
                return "редко"
            return None

        def is_stale(last_used: datetime | None) -> bool:
            if not last_used:
                return False
            # Storage may hand back naive datetimes (SQLite round-trip or
            # timezone=False columns); comparing naive against aware now()
            # raises TypeError and breaks the whole listing. Normalize.
            last_used = (
                last_used if last_used.tzinfo else last_used.replace(tzinfo=UTC)
            )
            return last_used < datetime.now(UTC) - timedelta(days=STALE_MONTHS * 30)

        # Build response
        response_templates = [
            DoctorSectionTemplateResponse(
                id=t.id,
                section_type=t.section_type,
                icd10_code=t.icd10_code,
                template_text=t.template_text,
                usage_count=t.usage_count,
                is_pinned=t.is_pinned,
                frequency_label=get_frequency_label(t.usage_count),
                is_stale=is_stale(t.last_used_at),
                last_used_at=t.last_used_at,
                created_at=t.created_at,
            )
            for t in templates
        ]

        return DoctorSectionTemplatesListResponse(
            section_type=section_type,
            icd10_code=icd10_code,
            templates=response_templates,
            total=len(response_templates),
        )

        # EMRTMPL-API-001 (fail-closed): DB failures here must surface as real
        # errors (HTTP 5xx), never as a falsely successful empty listing.
        # Invalid section_type above is the only legitimate empty response.

    def pin_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> tuple[bool, str]:
        """
        Закрепить шаблон.

        Limit: MAX_PINNED_PER_SECTION per doctor+section.
        If exceeded, auto-unpins oldest.

        Returns:
            (success, message)
        """
        try:
            # Get template
            stmt = select(DoctorSectionTemplate).where(
                and_(
                    DoctorSectionTemplate.id == template_id,
                    DoctorSectionTemplate.doctor_id == doctor_id,
                )
            )
            result = self.db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                return False, "Шаблон не найден"

            if template.is_pinned:
                return True, "Уже закреплён"

            # Count current pinned for this section
            count_stmt = select(func.count()).where(
                and_(
                    DoctorSectionTemplate.doctor_id == doctor_id,
                    DoctorSectionTemplate.section_type == template.section_type,
                    DoctorSectionTemplate.is_pinned == True,
                )
            )
            count_result = self.db.execute(count_stmt)
            pinned_count = count_result.scalar()

            # If limit exceeded, unpin oldest
            if pinned_count >= MAX_PINNED_PER_SECTION:
                oldest_stmt = (
                    select(DoctorSectionTemplate)
                    .where(
                        and_(
                            DoctorSectionTemplate.doctor_id == doctor_id,
                            DoctorSectionTemplate.section_type == template.section_type,
                            DoctorSectionTemplate.is_pinned == True,
                        )
                    )
                    .order_by(DoctorSectionTemplate.pinned_at.asc())
                    .limit(1)
                )
                oldest_result = self.db.execute(oldest_stmt)
                oldest = oldest_result.scalar_one_or_none()
                if oldest:
                    oldest.is_pinned = False
                    oldest.pinned_at = None

            # Pin the template
            template.is_pinned = True
            template.pinned_at = datetime.now(UTC)
            self.db.commit()

            return True, "Закреплён"

        except Exception as e:
            logger.error(f"Error in pin_template: {e}")
            self.db.rollback()
            return False, str(e)

    def unpin_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> tuple[bool, str]:
        """Открепить шаблон."""
        try:
            stmt = select(DoctorSectionTemplate).where(
                and_(
                    DoctorSectionTemplate.id == template_id,
                    DoctorSectionTemplate.doctor_id == doctor_id,
                )
            )
            result = self.db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                return False, "Шаблон не найден"

            template.is_pinned = False
            template.pinned_at = None
            self.db.commit()

            return True, "Откреплён"

        except Exception as e:
            logger.error(f"Error in unpin_template: {e}")
            self.db.rollback()
            return False, str(e)

    def update_template(
        self,
        doctor_id: int,
        template_id: str,
        new_text: str,
        mode: str = "replace",  # "replace" | "save_as_new"
    ) -> tuple[DoctorSectionTemplate | None, str]:
        """
        Обновить или создать новый шаблон.

        Args:
            doctor_id: ID врача
            template_id: ID исходного шаблона
            new_text: Новый текст
            mode:
                - "replace": обновить существующий шаблон
                - "save_as_new": создать новый шаблон с новым текстом

        Returns:
            (template, message)
        """
        if not new_text or not new_text.strip():
            return None, "Пустой текст"

        try:
            # Get original template
            stmt = select(DoctorSectionTemplate).where(
                and_(
                    DoctorSectionTemplate.id == template_id,
                    DoctorSectionTemplate.doctor_id == doctor_id,
                )
            )
            result = self.db.execute(stmt)
            original = result.scalar_one_or_none()

            if not original:
                return None, "Шаблон не найден"

            new_hash = DoctorSectionTemplate.compute_hash(new_text)

            if mode == "replace":
                # Update existing template
                original.template_text = new_text.strip()
                original.template_hash = new_hash
                original.last_used_at = datetime.now(UTC)
                self.db.commit()
                self.db.refresh(original)
                return original, "Обновлён"

            elif mode == "save_as_new":
                # Check if new text already exists
                check_stmt = select(DoctorSectionTemplate).where(
                    and_(
                        DoctorSectionTemplate.doctor_id == doctor_id,
                        DoctorSectionTemplate.section_type == original.section_type,
                        DoctorSectionTemplate.template_hash == new_hash,
                    )
                )
                check_result = self.db.execute(check_stmt)
                existing = check_result.scalar_one_or_none()

                if existing:
                    # Just increment usage
                    existing.usage_count += 1
                    existing.last_used_at = datetime.now(UTC)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing, "Такой шаблон уже есть, использование увеличено"

                # Create new template
                new_template = DoctorSectionTemplate(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor_id,
                    section_type=original.section_type,
                    icd10_code=original.icd10_code,
                    template_text=new_text.strip(),
                    template_hash=new_hash,
                    usage_count=1,
                    is_pinned=False,
                    last_used_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                )
                self.db.add(new_template)
                self.db.commit()
                self.db.refresh(new_template)
                return new_template, "Создан новый шаблон"

            else:
                return None, f"Неизвестный режим: {mode}"

        except Exception as e:
            logger.error(f"Error in update_template: {e}")
            self.db.rollback()
            return None, str(e)

    def delete_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> tuple[bool, str]:
        """Удалить шаблон (soft delete не нужен — hard delete)."""
        try:
            stmt = delete(DoctorSectionTemplate).where(
                and_(
                    DoctorSectionTemplate.id == template_id,
                    DoctorSectionTemplate.doctor_id == doctor_id,
                )
            )
            result = self.db.execute(stmt)
            self.db.commit()

            if result.rowcount > 0:
                return True, "Удалён"
            else:
                return False, "Не найден"

        except Exception as e:
            logger.error(f"Error in delete_template: {e}")
            self.db.rollback()
            return False, str(e)
