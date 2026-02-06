"""
Doctor Templates Service - персональная клиническая память врача

Сервис для обучения на подписанных EMR и рекомендаций лечения по диагнозу.

Принцип: AI = индекс + сортировка, НЕ генерация
Источник истины — реальная EMR история врача
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..models.doctor_templates import (
    DoctorTreatmentTemplate,
    DoctorTreatmentTemplateResponse,
    DoctorTreatmentTemplatesListResponse,
)

logger = logging.getLogger(__name__)


class DoctorTemplatesService:
    """
    Сервис для работы с персональными шаблонами лечения врача.
    
    Учится при подписании EMR, рекомендует по ICD-10 коду.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def learn_from_signed_emr(
        self,
        doctor_id: int,
        icd10_code: str,
        treatment_text: str,
    ) -> Optional[DoctorTreatmentTemplate]:
        """
        Обучение на подписанном EMR.
        
        Вызывается ТОЛЬКО когда:
        - EMR.status == "signed"
        - treatment_text не пустой
        - icd10_code указан
        
        Args:
            doctor_id: ID врача
            icd10_code: Код МКБ-10 (например, I10)
            treatment_text: Текст назначения
            
        Returns:
            Созданный или обновленный шаблон
        """
        if not treatment_text or not icd10_code:
            return None

        # Нормализация текста
        normalized = DoctorTreatmentTemplate.normalize_treatment(treatment_text)
        if not normalized:
            return None

        treatment_hash = DoctorTreatmentTemplate.compute_hash(normalized)

        try:
            # Проверяем существует ли такой шаблон (включая удалённые - для восстановления)
            stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                DoctorTreatmentTemplate.treatment_hash == treatment_hash,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Обновляем счетчик использования
                existing.usage_count += 1
                existing.last_used_at = datetime.utcnow()
                # Восстанавливаем если был удалён
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    logger.info(f"Restored soft-deleted template: {existing.id}")
                # Обновляем ICD код если изменился (один шаблон может применяться к разным диагнозам)
                if existing.icd10_code != icd10_code:
                    logger.info(
                        f"Template {existing.id} used for different ICD: "
                        f"{existing.icd10_code} -> {icd10_code}"
                    )
                await self.db.commit()
                logger.info(
                    f"Updated treatment template: doctor={doctor_id}, "
                    f"icd10={icd10_code}, usage_count={existing.usage_count}"
                )
                return existing
            else:
                # Создаем новый шаблон
                template = DoctorTreatmentTemplate(
                    id=str(uuid.uuid4()),
                    doctor_id=str(doctor_id),
                    icd10_code=icd10_code,
                    treatment_text=normalized,
                    treatment_hash=treatment_hash,
                    usage_count=1,
                    last_used_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                self.db.add(template)
                await self.db.commit()
                await self.db.refresh(template)
                logger.info(
                    f"Created treatment template: doctor={doctor_id}, "
                    f"icd10={icd10_code}, id={template.id}"
                )
                return template

        except Exception as e:
            logger.error(f"Error learning treatment pattern: {e}")
            await self.db.rollback()
            return None

    async def get_templates_by_diagnosis(
        self,
        doctor_id: int,
        icd10_code: str,
        limit: int = 5,
    ) -> DoctorTreatmentTemplatesListResponse:
        """
        Получить шаблоны лечения врача по диагнозу.
        
        Сортировка по usage_count DESC - часто используемые выше.
        
        Args:
            doctor_id: ID врача
            icd10_code: Код МКБ-10
            limit: Максимальное количество шаблонов
            
        Returns:
            Список шаблонов с метаданными
        """
        try:
            # Sorting: 📌 pinned first → 🔁 usage_count (часто) → 🕒 last_used
            stmt = (
                select(DoctorTreatmentTemplate)
                .where(
                    DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                    DoctorTreatmentTemplate.icd10_code == icd10_code,
                    DoctorTreatmentTemplate.is_deleted == False,
                )
                .order_by(
                    DoctorTreatmentTemplate.is_pinned.desc(),  # 📌 Pinned first
                    DoctorTreatmentTemplate.usage_count.desc(),  # 🔁 Frequent next
                )
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            templates = result.scalars().all()

            # Calculate frequency labels (no aggressive numbers)
            max_usage = max((t.usage_count for t in templates), default=0)
            
            def get_frequency_label(usage: int) -> Optional[str]:
                if max_usage <= 1:
                    return None
                if usage >= max_usage * 0.7:
                    return "часто"
                if usage <= max_usage * 0.3:
                    return "редко"
                return None

            # Calculate staleness: >12 months without use
            from datetime import timedelta
            stale_threshold = datetime.utcnow() - timedelta(days=365)
            
            def is_stale(last_used: datetime) -> bool:
                return last_used < stale_threshold

            return DoctorTreatmentTemplatesListResponse(
                source="doctor_history",
                icd10_code=icd10_code,
                templates=[
                    DoctorTreatmentTemplateResponse(
                        id=t.id,
                        icd10_code=t.icd10_code,
                        treatment_text=t.treatment_text,
                        usage_count=t.usage_count,
                        last_used_at=t.last_used_at,
                        is_pinned=t.is_pinned,
                        frequency_label=get_frequency_label(t.usage_count),
                        is_stale=is_stale(t.last_used_at),
                    )
                    for t in templates
                ],
                total=len(templates),
            )

        except Exception as e:
            logger.error(f"Error fetching treatment templates: {e}")
            return DoctorTreatmentTemplatesListResponse(
                source="doctor_history",
                icd10_code=icd10_code,
                templates=[],
                total=0,
            )

    async def delete_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> bool:
        """
        Удалить шаблон (врач может удалять свои шаблоны).
        
        Args:
            doctor_id: ID врача (для проверки владельца)
            template_id: ID шаблона
            
        Returns:
            True если удален, False если не найден или не владелец
        """
        try:
            stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.id == template_id,
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
            )
            result = await self.db.execute(stmt)
            template = result.scalar_one_or_none()

            if template:
                # Soft delete - врач может "передумать"
                template.is_deleted = True
                template.deleted_at = datetime.utcnow()
                await self.db.commit()
                logger.info(f"Soft-deleted treatment template: {template_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting treatment template: {e}")
            await self.db.rollback()
            return False

    async def get_all_templates_for_doctor(
        self,
        doctor_id: int,
        limit: int = 50,
    ) -> List[DoctorTreatmentTemplateResponse]:
        """
        Получить все шаблоны врача (для админ панели).
        """
        try:
            stmt = (
                select(DoctorTreatmentTemplate)
                .where(
                    DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                    DoctorTreatmentTemplate.is_deleted == False,  # ← Только активные
                )
                .order_by(DoctorTreatmentTemplate.usage_count.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            templates = result.scalars().all()

            return [
                DoctorTreatmentTemplateResponse(
                    id=t.id,
                    icd10_code=t.icd10_code,
                    treatment_text=t.treatment_text,
                    usage_count=t.usage_count,
                    last_used_at=t.last_used_at,
                    is_pinned=t.is_pinned,
                    frequency_label=None,
                )
                for t in templates
            ]

        except Exception as e:
            logger.error(f"Error fetching all templates: {e}")
            return []

    # ============== Pin/Unpin Methods ==============
    
    MAX_PINNED_PER_DIAGNOSIS = 3  # Hard limit
    
    async def pin_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> bool:
        """
        Закрепить шаблон (📌 Часто использую).
        
        Limit: max 3 pinned per doctor+diagnosis.
        If limit exceeded, auto-unpins oldest.
        """
        try:
            # Get template
            stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.id == template_id,
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                DoctorTreatmentTemplate.is_deleted == False,
            )
            result = await self.db.execute(stmt)
            template = result.scalar_one_or_none()
            
            if not template:
                return False
            
            if template.is_pinned:
                return True  # Already pinned
            
            # Count existing pinned for this diagnosis
            count_stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                DoctorTreatmentTemplate.icd10_code == template.icd10_code,
                DoctorTreatmentTemplate.is_pinned == True,
                DoctorTreatmentTemplate.is_deleted == False,
            )
            count_result = await self.db.execute(count_stmt)
            pinned_templates = count_result.scalars().all()
            
            # If at limit, unpin oldest
            if len(pinned_templates) >= self.MAX_PINNED_PER_DIAGNOSIS:
                oldest = min(pinned_templates, key=lambda t: t.pinned_at or datetime.min)
                oldest.is_pinned = False
                oldest.pinned_at = None
                logger.info(f"Auto-unpinned oldest template: {oldest.id}")
            
            # Pin this template
            template.is_pinned = True
            template.pinned_at = datetime.utcnow()
            
            await self.db.commit()
            logger.info(f"Pinned template: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error pinning template: {e}")
            await self.db.rollback()
            return False

    async def unpin_template(
        self,
        doctor_id: int,
        template_id: str,
    ) -> bool:
        """Открепить шаблон."""
        try:
            stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.id == template_id,
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
            )
            result = await self.db.execute(stmt)
            template = result.scalar_one_or_none()
            
            if not template:
                return False
            
            template.is_pinned = False
            template.pinned_at = None
            
            await self.db.commit()
            logger.info(f"Unpinned template: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unpinning template: {e}")
            await self.db.rollback()
            return False

    # ============== Edit Template Methods ==============

    async def update_template(
        self,
        doctor_id: int,
        template_id: str,
        new_text: str,
        mode: str = "replace",  # "replace" | "save_as_new"
    ) -> Optional[DoctorTreatmentTemplate]:
        """
        Обновить или создать новый шаблон на основе существующего.
        
        Args:
            doctor_id: ID врача
            template_id: ID исходного шаблона
            new_text: Новый текст назначения
            mode: "replace" - обновить текущий, "save_as_new" - создать новый
            
        Returns:
            Обновленный или новый шаблон
        """
        try:
            # Get original template
            stmt = select(DoctorTreatmentTemplate).where(
                DoctorTreatmentTemplate.id == template_id,
                DoctorTreatmentTemplate.doctor_id == str(doctor_id),
            )
            result = await self.db.execute(stmt)
            original = result.scalar_one_or_none()
            
            if not original:
                return None
            
            # Normalize new text
            normalized = DoctorTreatmentTemplate.normalize_treatment(new_text)
            if not normalized:
                return None
            
            new_hash = DoctorTreatmentTemplate.compute_hash(normalized)
            
            if mode == "save_as_new":
                # Create new template with same ICD-10
                # Check if already exists
                existing_stmt = select(DoctorTreatmentTemplate).where(
                    DoctorTreatmentTemplate.doctor_id == str(doctor_id),
                    DoctorTreatmentTemplate.treatment_hash == new_hash,
                )
                existing_result = await self.db.execute(existing_stmt)
                existing = existing_result.scalar_one_or_none()
                
                if existing:
                    # Already exists, just increment usage
                    existing.usage_count += 1
                    existing.last_used_at = datetime.utcnow()
                    if existing.is_deleted:
                        existing.is_deleted = False
                        existing.deleted_at = None
                    await self.db.commit()
                    return existing
                
                # Create new
                new_template = DoctorTreatmentTemplate(
                    id=str(uuid.uuid4()),
                    doctor_id=str(doctor_id),
                    icd10_code=original.icd10_code,
                    treatment_text=normalized,
                    treatment_hash=new_hash,
                    usage_count=1,
                    last_used_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    is_pinned=False,  # New template not pinned by default
                )
                self.db.add(new_template)
                await self.db.commit()
                await self.db.refresh(new_template)
                logger.info(f"Created new template from edit: {new_template.id}")
                return new_template
                
            else:  # mode == "replace"
                # Update existing template
                original.treatment_text = normalized
                original.treatment_hash = new_hash
                original.last_used_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(original)
                logger.info(f"Updated template: {template_id}")
                return original
                
        except Exception as e:
            logger.error(f"Error updating template: {e}")
            await self.db.rollback()
            return None

