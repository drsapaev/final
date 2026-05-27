import logging
from typing import Any, Dict, NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import deps
from app.models.cardio_blood_test import CardioBloodTest
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.schemas.cardio import CardioBloodTestCreate, CardioBloodTestOut

router = APIRouter(prefix="/cardio", tags=["cardio"])
logger = logging.getLogger(__name__)

CARDIO_ROLES = ("Admin", "Doctor", "cardio", "cardiology", "cardiologist", "Cardiologist")
CARDIO_PUBLIC_ERROR = "Internal server error"
CARDIO_ADMIN_ROLES = {"Admin"}


def _raise_cardio_internal_error(operation: str, exc: Exception) -> NoReturn:
    logger.warning(
        "[cardio] endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=CARDIO_PUBLIC_ERROR) from exc


def _is_admin_user(user: User) -> bool:
    return getattr(user, "role", None) in CARDIO_ADMIN_ROLES or bool(
        getattr(user, "is_superuser", False)
    )


def _doctor_allowed_doctor_ids(db: Session, user: User) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_doctor_ids.add(user.id)
    return allowed_doctor_ids


def _doctor_allowed_patient_ids(db: Session, user: User) -> set[int]:
    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, user)
    rows = (
        db.query(Visit.patient_id)
        .filter(
            Visit.doctor_id.in_(allowed_doctor_ids),
            Visit.patient_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _ensure_doctor_can_access_patient(db: Session, patient_id: int, user: User) -> None:
    if _is_admin_user(user):
        return
    if patient_id not in _doctor_allowed_patient_ids(db, user):
        raise HTTPException(status_code=403, detail="Access denied")


def _ensure_doctor_can_access_visit(db: Session, visit: Visit, user: User) -> None:
    if _is_admin_user(user):
        return
    if visit.doctor_id not in _doctor_allowed_doctor_ids(db, user):
        raise HTTPException(status_code=403, detail="Access denied")


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
        _raise_cardio_internal_error("get_ecg_results", e)


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
        _raise_cardio_internal_error("create_ecg", e)


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
        if not _is_admin_user(user):
            if patient_id is not None:
                _ensure_doctor_can_access_patient(db, patient_id, user)
            else:
                allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
                if not allowed_patient_ids:
                    return []
                query = query.filter(CardioBloodTest.patient_id.in_(allowed_patient_ids))

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
            "[cardio.blood-tests] listed tests user_id=%s filtered_by_patient=%s count=%s",
            getattr(user, "id", None),
            patient_id is not None,
            len(tests),
        )
        return tests
    except SQLAlchemyError as e:
        _raise_cardio_internal_error("get_blood_tests", e)


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

        if blood_test_data.visit_id is None:
            _ensure_doctor_can_access_patient(db, blood_test_data.patient_id, user)
        else:
            _ensure_doctor_can_access_visit(db, visit, user)

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
            "[cardio.blood-tests] created test_id=%s visit_id=%s user_id=%s",
            blood_test.id,
            blood_test.visit_id,
            getattr(user, "id", None),
        )
        return blood_test
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        _raise_cardio_internal_error("create_blood_test", e)


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
        _raise_cardio_internal_error("get_risk_assessment", e)
