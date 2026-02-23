from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User

router = APIRouter(prefix="/lab", tags=["lab_specialized"])


@router.get("/tests", summary="Лабораторные исследования")
async def get_lab_tests(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список лабораторных исследований
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения исследований: {str(e)}"
        )


@router.post("/tests", summary="Создать лабораторное исследование")
async def create_lab_test(
    test_data: dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab")),
) -> dict[str, Any]:
    """
    Создать новое лабораторное исследование
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Лабораторное исследование создано", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания исследования: {str(e)}"
        )


@router.get("/results", summary="Результаты анализов")
async def get_lab_results(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список результатов анализов
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения результатов: {str(e)}"
        )


@router.post("/results", summary="Создать результат анализа")
async def create_lab_result(
    result_data: dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab")),
) -> dict[str, Any]:
    """
    Создать новый результат анализа
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Результат анализа создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания результата: {str(e)}"
        )


@router.get("/reports", summary="Лабораторные отчеты")
async def get_lab_reports(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab")),
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Получить лабораторные отчеты за период
    """
    try:
        return {"message": "Модуль отчетов будет доступен в следующей версии"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения отчетов: {str(e)}"
        )


@router.get("/reference-ranges", summary="Референсные значения")
async def get_reference_ranges(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab", "Doctor")),
) -> dict[str, Any]:
    """
    Получить референсные значения для анализов
    """
    try:
        return {
            "cbc": {
                "hemoglobin": {"male": "130-170 g/L", "female": "120-150 g/L"},
                "leukocytes": "4.0-9.0 × 10⁹/L",
                "platelets": "150-400 × 10⁹/L",
            },
            "biochemical": {
                "glucose": "3.3-5.5 mmol/L",
                "cholesterol": "<5.0 mmol/L",
                "creatinine": {"male": "62-106 µmol/L", "female": "44-80 µmol/L"},
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения референсных значений: {str(e)}"
        )


@router.get("/equipment", summary="Лабораторное оборудование")
async def get_lab_equipment(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Lab")),
) -> dict[str, Any]:
    """
    Получить статус лабораторного оборудования
    """
    try:
        return {"message": "Модуль оборудования будет доступен в следующей версии"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статуса оборудования: {str(e)}"
        )
