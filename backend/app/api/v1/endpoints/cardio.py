import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import deps
from app.models.cardio_blood_test import CardioBloodTest
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.schemas.cardio import CardioBloodTestCreate, CardioBloodTestOut

router = APIRouter(prefix="/cardio", tags=["cardio"])
logger = logging.getLogger(__name__)

CARDIO_ROLES = ("Admin", "Doctor", "cardio", "cardiology", "cardiologist", "Cardiologist")


@router.get("/ecg", summary="ЭКГ исследования")
async def get_ecg_results(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*CARDIO_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """
    Получить список ЭКГ исследований
    """
    try:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения ЭКГ: {str(e)}")


@router.post("/ecg", summary="Создать ЭКГ исследование")
async def create_ecg(
    ecg_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*CARDIO_ROLES)),
) -> Dict[str, Any]:
    """
    Создать новое ЭКГ исследование
    """
    try:
        return {"message": "ЭКГ исследование создано", "id": 1}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания ЭКГ: {str(e)}")


@router.get(
    "/blood-tests",
    summary="Анализы крови",
    response_model=list[CardioBloodTestOut],
)
async def get_blood_tests(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*CARDIO_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
) -> list[CardioBloodTestOut]:
    """
    Получить список анализов крови
    """
    try:
        query = db.query(CardioBloodTest)
        if patient_id is not None:
            query = query.filter(CardioBloodTest.patient_id == patient_id)

        tests = (
            query.order_by(
                desc(CardioBloodTest.test_date),
                desc(CardioBloodTest.created_at),
                desc(CardioBloodTest.id),
            )
            .limit(limit)
            .all()
        )
        logger.info(
            "[cardio.blood-tests] listed tests user_id=%s patient_id=%s count=%s",
            getattr(user, "id", None),
            patient_id,
            len(tests),
        )
        return tests
    except SQLAlchemyError as e:
        logger.exception(
            "[cardio.blood-tests] failed to list tests user_id=%s patient_id=%s",
            getattr(user, "id", None),
            patient_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения анализов крови: {str(e)}"
        )


@router.post(
    "/blood-tests",
    summary="Создать анализ крови",
    response_model=CardioBloodTestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_blood_test(
    blood_test_data: CardioBloodTestCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*CARDIO_ROLES)),
) -> CardioBloodTestOut:
    """
    Создать новый анализ крови
    """
    try:
        patient = db.get(Patient, blood_test_data.patient_id)
        if patient is None:
            raise HTTPException(status_code=404, detail="Пациент не найден")

        if blood_test_data.visit_id is not None:
            visit = db.get(Visit, blood_test_data.visit_id)
            if visit is None:
                raise HTTPException(status_code=404, detail="Визит не найден")
            if visit.patient_id != blood_test_data.patient_id:
                raise HTTPException(
                    status_code=400,
                    detail="Визит не принадлежит выбранному пациенту",
                )

        blood_test = CardioBloodTest(
            patient_id=blood_test_data.patient_id,
            visit_id=blood_test_data.visit_id,
            doctor_id=getattr(user, "id", None),
            test_date=blood_test_data.test_date,
            cholesterol_total=blood_test_data.cholesterol_total,
            cholesterol_hdl=blood_test_data.cholesterol_hdl,
            cholesterol_ldl=blood_test_data.cholesterol_ldl,
            triglycerides=blood_test_data.triglycerides,
            glucose=blood_test_data.glucose,
            crp=blood_test_data.crp,
            troponin=blood_test_data.troponin,
            interpretation=blood_test_data.interpretation,
        )
        db.add(blood_test)
        db.commit()
        db.refresh(blood_test)
        logger.info(
            "[cardio.blood-tests] created test_id=%s patient_id=%s visit_id=%s user_id=%s",
            blood_test.id,
            blood_test.patient_id,
            blood_test.visit_id,
            getattr(user, "id", None),
        )
        return blood_test
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception(
            "[cardio.blood-tests] failed to create test user_id=%s patient_id=%s visit_id=%s",
            getattr(user, "id", None),
            blood_test_data.patient_id,
            blood_test_data.visit_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания анализа крови: {str(e)}"
        )


@router.get("/risk-assessment", summary="Оценка рисков")
async def get_risk_assessment(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*CARDIO_ROLES)),
    patient_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить оценку кардиологических рисков
    """
    try:
        return {"message": "Модуль оценки рисков будет доступен в следующей версии"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения оценки рисков: {str(e)}"
        )
