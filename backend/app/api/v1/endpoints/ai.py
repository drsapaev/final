"""
AI API endpoints
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ....api.deps import get_current_user
from ....models.user import User
from ....services.ai import ai_manager, AIProviderType
from ....services.mcp import get_mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ComplaintAnalysisRequest(BaseModel):
    """Запрос на анализ жалоб"""

    complaint: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None
    use_mcp: bool = True  # Использовать MCP по умолчанию


class ICD10SuggestRequest(BaseModel):
    """Запрос на подсказки МКБ-10"""

    symptoms: List[str]
    diagnosis: Optional[str] = None
    provider: Optional[AIProviderType] = None


class LabInterpretRequest(BaseModel):
    """Запрос на интерпретацию анализов"""

    results: List[Dict[str, Any]]
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None


class ECGInterpretRequest(BaseModel):
    """Запрос на интерпретацию ЭКГ"""

    parameters: Dict[str, Any]
    auto_interpretation: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None


@router.get("/providers")
async def get_available_providers(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Получить список доступных AI провайдеров"""
    return {
        "providers": ai_manager.get_available_providers(),
        "default": (
            ai_manager.default_provider.value if ai_manager.default_provider else None
        ),
    }


@router.post("/complaint-to-plan")
async def analyze_complaint(
    request: ComplaintAnalysisRequest, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Анализ жалоб пациента и создание плана обследования"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender

        # Используем MCP если включено
        if request.use_mcp:
            try:
                mcp_manager = await get_mcp_manager()
                result = await mcp_manager.execute_request(
                    server="complaint",
                    method="tool/analyze_complaint",
                    params={
                        "complaint": request.complaint,
                        "patient_info": patient_info if patient_info else None,
                        "provider": (
                            request.provider.value if request.provider else None
                        ),
                        "urgency_assessment": True,
                    },
                )

                if result.get("status") == "success":
                    return result.get("data", {})
                elif result.get("fallback"):
                    # Fallback to direct AI manager
                    logger.warning("MCP failed, falling back to direct AI manager")
                else:
                    raise HTTPException(
                        status_code=500, detail=result.get("error", "MCP error")
                    )
            except Exception as mcp_error:
                logger.error(f"MCP error: {str(mcp_error)}")
                # Fallback to direct AI manager if MCP fails

        # Direct AI manager call (fallback or if MCP disabled)
        result = await ai_manager.analyze_complaint(
            complaint=request.complaint,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error analyzing complaint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/icd-suggest")
async def suggest_icd10_codes(
    request: ICD10SuggestRequest, current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Получить подсказки кодов МКБ-10"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        result = await ai_manager.suggest_icd10(
            symptoms=request.symptoms,
            diagnosis=request.diagnosis,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error suggesting ICD-10: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lab-interpret")
async def interpret_lab_results(
    request: LabInterpretRequest, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Интерпретация результатов лабораторных анализов"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "lab", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender

        result = await ai_manager.interpret_lab_results(
            results=request.results,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error interpreting lab results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skin-analyze")
async def analyze_skin(
    image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Анализ состояния кожи по фото"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Проверяем тип файла
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")

        # Читаем изображение
        image_data = await image.read()

        # Парсим метаданные если есть
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except:
                metadata_dict = {"description": metadata}

        result = await ai_manager.analyze_skin(
            image_data=image_data, metadata=metadata_dict, provider_type=provider
        )

        return result

    except Exception as e:
        logger.error(f"Error analyzing skin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ecg-interpret")
async def interpret_ecg(
    request: ECGInterpretRequest, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Интерпретация данных ЭКГ"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender

        ecg_data = {
            "parameters": request.parameters,
            "auto_interpretation": request.auto_interpretation,
        }

        result = await ai_manager.interpret_ecg(
            ecg_data=ecg_data,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error interpreting ECG: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class DifferentialDiagnosisRequest(BaseModel):
    """Запрос на дифференциальную диагностику"""

    symptoms: List[str]
    patient_info: Optional[Dict[str, Any]] = None
    provider: Optional[AIProviderType] = None


class SymptomAnalysisRequest(BaseModel):
    """Запрос на анализ симптомов"""

    symptoms: List[str]
    severity: Optional[List[int]] = None
    provider: Optional[AIProviderType] = None


class ClinicalDecisionRequest(BaseModel):
    """Запрос на поддержку клинических решений"""

    case_data: Dict[str, Any]
    provider: Optional[AIProviderType] = None


@router.post("/differential-diagnosis")
async def differential_diagnosis(
    request: DifferentialDiagnosisRequest,
    current_user: User = Depends(get_current_user),
):
    """Дифференциальная диагностика"""
    try:
        result = await ai_manager.differential_diagnosis(
            symptoms=request.symptoms,
            patient_info=request.patient_info,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка дифференциальной диагностики: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symptom-analysis")
async def symptom_analysis(
    request: SymptomAnalysisRequest, current_user: User = Depends(get_current_user)
):
    """Расширенный анализ симптомов"""
    try:
        result = await ai_manager.symptom_analysis(
            symptoms=request.symptoms,
            severity=request.severity,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа симптомов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clinical-decision-support")
async def clinical_decision_support(
    request: ClinicalDecisionRequest, current_user: User = Depends(get_current_user)
):
    """Поддержка клинических решений"""
    try:
        result = await ai_manager.clinical_decision_support(
            case_data=request.case_data, provider=request.provider
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка поддержки клинических решений: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class MedicalImageAnalysisRequest(BaseModel):
    """Запрос на анализ медицинского изображения"""

    image_type: str  # xray, ultrasound, dermatoscopy, generic
    metadata: Optional[Dict[str, Any]] = None
    provider: Optional[AIProviderType] = None


@router.post("/analyze-xray")
async def analyze_xray_image(
    image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Анализ рентгеновского снимка"""
    try:
        # Читаем изображение
        image_data = await image.read()

        # Парсим метаданные
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Неверный формат метаданных"
                )

        # Анализируем изображение
        result = await ai_manager.analyze_xray_image(
            image_data=image_data, metadata=metadata_dict, provider=provider
        )

        return result

    except Exception as e:
        logger.error(f"Ошибка анализа рентгеновского снимка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-ultrasound")
async def analyze_ultrasound_image(
    image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Анализ УЗИ изображения"""
    try:
        # Читаем изображение
        image_data = await image.read()

        # Парсим метаданные
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Неверный формат метаданных"
                )

        # Анализируем изображение
        result = await ai_manager.analyze_ultrasound_image(
            image_data=image_data, metadata=metadata_dict, provider=provider
        )

        return result

    except Exception as e:
        logger.error(f"Ошибка анализа УЗИ изображения: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-dermatoscopy")
async def analyze_dermatoscopy_image(
    image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Анализ дерматоскопического изображения"""
    try:
        # Читаем изображение
        image_data = await image.read()

        # Парсим метаданные
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Неверный формат метаданных"
                )

        # Анализируем изображение
        result = await ai_manager.analyze_dermatoscopy_image(
            image_data=image_data, metadata=metadata_dict, provider=provider
        )

        return result

    except Exception as e:
        logger.error(f"Ошибка анализа дерматоскопического изображения: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-medical-image")
async def analyze_medical_image_generic(
    image: UploadFile = File(...),
    image_type: str = Form(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Универсальный анализ медицинского изображения"""
    try:
        # Читаем изображение
        image_data = await image.read()

        # Парсим метаданные
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Неверный формат метаданных"
                )

        # Анализируем изображение
        result = await ai_manager.analyze_medical_image_generic(
            image_data=image_data,
            image_type=image_type,
            metadata=metadata_dict,
            provider=provider,
        )

        return result

    except Exception as e:
        logger.error(f"Ошибка анализа медицинского изображения: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class TreatmentPlanRequest(BaseModel):
    """Запрос на генерацию плана лечения"""

    patient_data: Dict[str, Any]
    diagnosis: str
    medical_history: Optional[List[Dict[str, Any]]] = None
    provider: Optional[AIProviderType] = None


class MedicationOptimizationRequest(BaseModel):
    """Запрос на оптимизацию медикаментозной терапии"""

    current_medications: List[Dict[str, Any]]
    patient_profile: Dict[str, Any]
    condition: str
    provider: Optional[AIProviderType] = None


class TreatmentEffectivenessRequest(BaseModel):
    """Запрос на оценку эффективности лечения"""

    treatment_history: List[Dict[str, Any]]
    patient_response: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class LifestyleModificationsRequest(BaseModel):
    """Запрос на рекомендации по образу жизни"""

    patient_profile: Dict[str, Any]
    conditions: List[str]
    provider: Optional[AIProviderType] = None


@router.post("/generate-treatment-plan")
async def generate_treatment_plan(
    request: TreatmentPlanRequest, current_user: User = Depends(get_current_user)
):
    """Генерация персонализированного плана лечения"""
    try:
        result = await ai_manager.generate_treatment_plan(
            patient_data=request.patient_data,
            diagnosis=request.diagnosis,
            medical_history=request.medical_history,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка генерации плана лечения: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-medication")
async def optimize_medication_regimen(
    request: MedicationOptimizationRequest,
    current_user: User = Depends(get_current_user),
):
    """Оптимизация медикаментозной терапии"""
    try:
        result = await ai_manager.optimize_medication_regimen(
            current_medications=request.current_medications,
            patient_profile=request.patient_profile,
            condition=request.condition,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка оптимизации медикаментозной терапии: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assess-treatment-effectiveness")
async def assess_treatment_effectiveness(
    request: TreatmentEffectivenessRequest,
    current_user: User = Depends(get_current_user),
):
    """Оценка эффективности лечения"""
    try:
        result = await ai_manager.assess_treatment_effectiveness(
            treatment_history=request.treatment_history,
            patient_response=request.patient_response,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка оценки эффективности лечения: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-lifestyle-modifications")
async def suggest_lifestyle_modifications(
    request: LifestyleModificationsRequest,
    current_user: User = Depends(get_current_user),
):
    """Рекомендации по изменению образа жизни"""
    try:
        result = await ai_manager.suggest_lifestyle_modifications(
            patient_profile=request.patient_profile,
            conditions=request.conditions,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка генерации рекомендаций по образу жизни: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class DrugInteractionRequest(BaseModel):
    """Запрос на проверку лекарственных взаимодействий"""

    medications: List[Dict[str, Any]]
    patient_profile: Optional[Dict[str, Any]] = None
    provider: Optional[AIProviderType] = None


class DrugSafetyRequest(BaseModel):
    """Запрос на анализ безопасности препарата"""

    medication: Dict[str, Any]
    patient_profile: Dict[str, Any]
    conditions: List[str]
    provider: Optional[AIProviderType] = None


class DrugAlternativesRequest(BaseModel):
    """Запрос на предложение альтернативных препаратов"""

    medication: str
    reason: str
    patient_profile: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class DrugDosageRequest(BaseModel):
    """Запрос на расчет дозировки препарата"""

    medication: str
    patient_profile: Dict[str, Any]
    indication: str
    provider: Optional[AIProviderType] = None


@router.post("/check-drug-interactions")
async def check_drug_interactions(
    request: DrugInteractionRequest, current_user: User = Depends(get_current_user)
):
    """Проверка лекарственных взаимодействий"""
    try:
        result = await ai_manager.check_drug_interactions(
            medications=request.medications,
            patient_profile=request.patient_profile,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка проверки лекарственных взаимодействий: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-drug-safety")
async def analyze_drug_safety(
    request: DrugSafetyRequest, current_user: User = Depends(get_current_user)
):
    """Анализ безопасности препарата для конкретного пациента"""
    try:
        result = await ai_manager.analyze_drug_safety(
            medication=request.medication,
            patient_profile=request.patient_profile,
            conditions=request.conditions,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа безопасности препарата: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-drug-alternatives")
async def suggest_drug_alternatives(
    request: DrugAlternativesRequest, current_user: User = Depends(get_current_user)
):
    """Предложение альтернативных препаратов"""
    try:
        result = await ai_manager.suggest_drug_alternatives(
            medication=request.medication,
            reason=request.reason,
            patient_profile=request.patient_profile,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка предложения альтернативных препаратов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-drug-dosage")
async def calculate_drug_dosage(
    request: DrugDosageRequest, current_user: User = Depends(get_current_user)
):
    """Расчет дозировки препарата"""
    try:
        result = await ai_manager.calculate_drug_dosage(
            medication=request.medication,
            patient_profile=request.patient_profile,
            indication=request.indication,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка расчета дозировки препарата: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class RiskAssessmentRequest(BaseModel):
    """Запрос на комплексную оценку рисков пациента"""

    patient_data: Dict[str, Any]
    risk_factors: List[str]
    condition: str
    provider: Optional[AIProviderType] = None


class ComplicationPredictionRequest(BaseModel):
    """Запрос на прогнозирование осложнений"""

    patient_profile: Dict[str, Any]
    procedure_or_condition: str
    timeline: str
    provider: Optional[AIProviderType] = None


class MortalityRiskRequest(BaseModel):
    """Запрос на расчет риска смертности"""

    patient_data: Dict[str, Any]
    condition: str
    scoring_system: Optional[str] = None
    provider: Optional[AIProviderType] = None


class SurgicalRiskRequest(BaseModel):
    """Запрос на оценку хирургических рисков"""

    patient_profile: Dict[str, Any]
    surgery_type: str
    anesthesia_type: str
    provider: Optional[AIProviderType] = None


class ReadmissionRiskRequest(BaseModel):
    """Запрос на прогнозирование риска повторной госпитализации"""

    patient_data: Dict[str, Any]
    discharge_condition: str
    social_factors: Dict[str, Any]
    provider: Optional[AIProviderType] = None


@router.post("/assess-patient-risk")
async def assess_patient_risk(
    request: RiskAssessmentRequest, current_user: User = Depends(get_current_user)
):
    """Комплексная оценка рисков пациента"""
    try:
        result = await ai_manager.assess_patient_risk(
            patient_data=request.patient_data,
            risk_factors=request.risk_factors,
            condition=request.condition,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка оценки рисков пациента: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-complications")
async def predict_complications(
    request: ComplicationPredictionRequest,
    current_user: User = Depends(get_current_user),
):
    """Прогнозирование возможных осложнений"""
    try:
        result = await ai_manager.predict_complications(
            patient_profile=request.patient_profile,
            procedure_or_condition=request.procedure_or_condition,
            timeline=request.timeline,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка прогнозирования осложнений: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-mortality-risk")
async def calculate_mortality_risk(
    request: MortalityRiskRequest, current_user: User = Depends(get_current_user)
):
    """Расчет риска смертности"""
    try:
        result = await ai_manager.calculate_mortality_risk(
            patient_data=request.patient_data,
            condition=request.condition,
            scoring_system=request.scoring_system,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка расчета риска смертности: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assess-surgical-risk")
async def assess_surgical_risk(
    request: SurgicalRiskRequest, current_user: User = Depends(get_current_user)
):
    """Оценка хирургических рисков"""
    try:
        result = await ai_manager.assess_surgical_risk(
            patient_profile=request.patient_profile,
            surgery_type=request.surgery_type,
            anesthesia_type=request.anesthesia_type,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка оценки хирургических рисков: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-readmission-risk")
async def predict_readmission_risk(
    request: ReadmissionRiskRequest, current_user: User = Depends(get_current_user)
):
    """Прогнозирование риска повторной госпитализации"""
    try:
        result = await ai_manager.predict_readmission_risk(
            patient_data=request.patient_data,
            discharge_condition=request.discharge_condition,
            social_factors=request.social_factors,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка прогнозирования риска повторной госпитализации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class AudioTranscriptionRequest(BaseModel):
    """Запрос на транскрипцию аудио"""

    language: str = "ru"
    medical_context: bool = True
    provider: Optional[AIProviderType] = None


class TextStructuringRequest(BaseModel):
    """Запрос на структурирование медицинского текста"""

    text: str
    document_type: str  # consultation, prescription, discharge, examination
    provider: Optional[AIProviderType] = None


class EntityExtractionRequest(BaseModel):
    """Запрос на извлечение медицинских сущностей"""

    text: str
    provider: Optional[AIProviderType] = None


class MedicalSummaryRequest(BaseModel):
    """Запрос на генерацию медицинского резюме"""

    consultation_text: str
    patient_history: Optional[str] = None
    provider: Optional[AIProviderType] = None


class RecordValidationRequest(BaseModel):
    """Запрос на валидацию медицинской записи"""

    record_data: Dict[str, Any]
    provider: Optional[AIProviderType] = None


@router.post("/transcribe-audio")
async def transcribe_audio(
    request: AudioTranscriptionRequest,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Транскрипция аудио в текст с медицинской терминологией"""
    try:
        # Проверяем тип файла
        if not audio_file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="Файл должен быть аудио")

        # Читаем аудио данные
        audio_data = await audio_file.read()

        # Ограничиваем размер файла (например, 25 МБ)
        if len(audio_data) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="Файл слишком большой (максимум 25 МБ)"
            )

        result = await ai_manager.transcribe_audio(
            audio_data=audio_data,
            language=request.language,
            medical_context=request.medical_context,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка транскрипции аудио: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/structure-medical-text")
async def structure_medical_text(
    request: TextStructuringRequest, current_user: User = Depends(get_current_user)
):
    """Структурирование медицинского текста в формализованные поля"""
    try:
        result = await ai_manager.structure_medical_text(
            text=request.text,
            document_type=request.document_type,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка структурирования текста: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-medical-entities")
async def extract_medical_entities(
    request: EntityExtractionRequest, current_user: User = Depends(get_current_user)
):
    """Извлечение медицинских сущностей из текста"""
    try:
        result = await ai_manager.extract_medical_entities(
            text=request.text, provider=request.provider
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка извлечения медицинских сущностей: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-medical-summary")
async def generate_medical_summary(
    request: MedicalSummaryRequest, current_user: User = Depends(get_current_user)
):
    """Генерация медицинского резюме из текста консультации"""
    try:
        result = await ai_manager.generate_medical_summary(
            consultation_text=request.consultation_text,
            patient_history=request.patient_history,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка генерации медицинского резюме: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-medical-record")
async def validate_medical_record(
    request: RecordValidationRequest, current_user: User = Depends(get_current_user)
):
    """Валидация и проверка медицинской записи на полноту и корректность"""
    try:
        result = await ai_manager.validate_medical_record(
            record_data=request.record_data, provider=request.provider
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка валидации медицинской записи: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ScheduleOptimizationRequest(BaseModel):
    """Запрос на оптимизацию расписания врача"""

    schedule_data: Dict[str, Any]
    constraints: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class AppointmentDurationRequest(BaseModel):
    """Запрос на прогнозирование длительности приема"""

    appointment_data: Dict[str, Any]
    historical_data: List[Dict[str, Any]]
    provider: Optional[AIProviderType] = None


class OptimalSlotsRequest(BaseModel):
    """Запрос на предложение оптимальных временных слотов"""

    doctor_profile: Dict[str, Any]
    patient_requirements: Dict[str, Any]
    available_slots: List[Dict[str, Any]]
    provider: Optional[AIProviderType] = None


class WorkloadAnalysisRequest(BaseModel):
    """Запрос на анализ распределения рабочей нагрузки"""

    doctors_data: List[Dict[str, Any]]
    time_period: str
    provider: Optional[AIProviderType] = None


class ShiftRecommendationsRequest(BaseModel):
    """Запрос на генерацию рекомендаций по составлению смен"""

    department_data: Dict[str, Any]
    staffing_requirements: Dict[str, Any]
    provider: Optional[AIProviderType] = None


@router.post("/optimize-doctor-schedule")
async def optimize_doctor_schedule(
    request: ScheduleOptimizationRequest, current_user: User = Depends(get_current_user)
):
    """Оптимизация расписания врача с учетом ограничений и предпочтений"""
    try:
        result = await ai_manager.optimize_doctor_schedule(
            schedule_data=request.schedule_data,
            constraints=request.constraints,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка оптимизации расписания врача: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-appointment-duration")
async def predict_appointment_duration(
    request: AppointmentDurationRequest, current_user: User = Depends(get_current_user)
):
    """Прогнозирование длительности приема на основе исторических данных"""
    try:
        result = await ai_manager.predict_appointment_duration(
            appointment_data=request.appointment_data,
            historical_data=request.historical_data,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка прогнозирования длительности приема: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-optimal-slots")
async def suggest_optimal_slots(
    request: OptimalSlotsRequest, current_user: User = Depends(get_current_user)
):
    """Предложение оптимальных временных слотов для записи"""
    try:
        result = await ai_manager.suggest_optimal_slots(
            doctor_profile=request.doctor_profile,
            patient_requirements=request.patient_requirements,
            available_slots=request.available_slots,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка предложения оптимальных слотов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-workload-distribution")
async def analyze_workload_distribution(
    request: WorkloadAnalysisRequest, current_user: User = Depends(get_current_user)
):
    """Анализ распределения рабочей нагрузки между врачами"""
    try:
        result = await ai_manager.analyze_workload_distribution(
            doctors_data=request.doctors_data,
            time_period=request.time_period,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа распределения нагрузки: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-shift-recommendations")
async def generate_shift_recommendations(
    request: ShiftRecommendationsRequest, current_user: User = Depends(get_current_user)
):
    """Генерация рекомендаций по составлению смен и графиков работы"""
    try:
        result = await ai_manager.generate_shift_recommendations(
            department_data=request.department_data,
            staffing_requirements=request.staffing_requirements,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка генерации рекомендаций по сменам: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class DocumentationQualityRequest(BaseModel):
    """Запрос на анализ качества медицинской документации"""

    medical_records: List[Dict[str, Any]]
    quality_standards: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class DocumentationGapsRequest(BaseModel):
    """Запрос на выявление пробелов в документации"""

    patient_record: Dict[str, Any]
    required_fields: List[str]
    provider: Optional[AIProviderType] = None


class DocumentationImprovementsRequest(BaseModel):
    """Запрос на предложение улучшений документации"""

    record_analysis: Dict[str, Any]
    best_practices: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class ClinicalConsistencyRequest(BaseModel):
    """Запрос на валидацию клинической согласованности"""

    diagnosis: str
    symptoms: List[str]
    treatment: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class PrescriptionSafetyRequest(BaseModel):
    """Запрос на аудит безопасности назначений"""

    prescriptions: List[Dict[str, Any]]
    patient_profile: Dict[str, Any]
    provider: Optional[AIProviderType] = None


@router.post("/analyze-documentation-quality")
async def analyze_documentation_quality(
    request: DocumentationQualityRequest, current_user: User = Depends(get_current_user)
):
    """Анализ качества медицинской документации"""
    try:
        result = await ai_manager.analyze_documentation_quality(
            medical_records=request.medical_records,
            quality_standards=request.quality_standards,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа качества документации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-documentation-gaps")
async def detect_documentation_gaps(
    request: DocumentationGapsRequest, current_user: User = Depends(get_current_user)
):
    """Выявление пробелов в медицинской документации"""
    try:
        result = await ai_manager.detect_documentation_gaps(
            patient_record=request.patient_record,
            required_fields=request.required_fields,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка выявления пробелов в документации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-documentation-improvements")
async def suggest_documentation_improvements(
    request: DocumentationImprovementsRequest,
    current_user: User = Depends(get_current_user),
):
    """Предложение улучшений для медицинской документации"""
    try:
        result = await ai_manager.suggest_documentation_improvements(
            record_analysis=request.record_analysis,
            best_practices=request.best_practices,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка предложения улучшений документации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-clinical-consistency")
async def validate_clinical_consistency(
    request: ClinicalConsistencyRequest, current_user: User = Depends(get_current_user)
):
    """Валидация клинической согласованности диагноза, симптомов и лечения"""
    try:
        result = await ai_manager.validate_clinical_consistency(
            diagnosis=request.diagnosis,
            symptoms=request.symptoms,
            treatment=request.treatment,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка валидации клинической согласованности: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit-prescription-safety")
async def audit_prescription_safety(
    request: PrescriptionSafetyRequest, current_user: User = Depends(get_current_user)
):
    """Аудит безопасности назначений и рецептов"""
    try:
        result = await ai_manager.audit_prescription_safety(
            prescriptions=request.prescriptions,
            patient_profile=request.patient_profile,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка аудита безопасности назначений: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class MedicalTrendsRequest(BaseModel):
    """Запрос на анализ медицинских трендов"""

    medical_data: List[Dict[str, Any]]
    time_period: str
    analysis_type: str
    provider: Optional[AIProviderType] = None


class AnomalyDetectionRequest(BaseModel):
    """Запрос на выявление аномалий"""

    dataset: List[Dict[str, Any]]
    baseline_data: Dict[str, Any]
    provider: Optional[AIProviderType] = None


class OutcomePredictionRequest(BaseModel):
    """Запрос на прогнозирование исходов"""

    patient_data: Dict[str, Any]
    historical_outcomes: List[Dict[str, Any]]
    provider: Optional[AIProviderType] = None


class InsightsReportRequest(BaseModel):
    """Запрос на генерацию отчета с инсайтами"""

    analytics_data: Dict[str, Any]
    report_type: str
    provider: Optional[AIProviderType] = None


class RiskPatternsRequest(BaseModel):
    """Запрос на выявление паттернов рисков"""

    population_data: List[Dict[str, Any]]
    risk_factors: List[str]
    provider: Optional[AIProviderType] = None


@router.post("/analyze-medical-trends")
async def analyze_medical_trends(
    request: MedicalTrendsRequest, current_user: User = Depends(get_current_user)
):
    """Анализ медицинских трендов и паттернов в данных"""
    try:
        result = await ai_manager.analyze_medical_trends(
            medical_data=request.medical_data,
            time_period=request.time_period,
            analysis_type=request.analysis_type,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа медицинских трендов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-anomalies")
async def detect_anomalies(
    request: AnomalyDetectionRequest, current_user: User = Depends(get_current_user)
):
    """Выявление аномалий в медицинских данных"""
    try:
        result = await ai_manager.detect_anomalies(
            dataset=request.dataset,
            baseline_data=request.baseline_data,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка выявления аномалий: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-outcomes")
async def predict_outcomes(
    request: OutcomePredictionRequest, current_user: User = Depends(get_current_user)
):
    """Прогнозирование медицинских исходов на основе данных"""
    try:
        result = await ai_manager.predict_outcomes(
            patient_data=request.patient_data,
            historical_outcomes=request.historical_outcomes,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка прогнозирования исходов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-insights-report")
async def generate_insights_report(
    request: InsightsReportRequest, current_user: User = Depends(get_current_user)
):
    """Генерация отчета с аналитическими инсайтами"""
    try:
        result = await ai_manager.generate_insights_report(
            analytics_data=request.analytics_data,
            report_type=request.report_type,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка генерации отчета с инсайтами: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identify-risk-patterns")
async def identify_risk_patterns(
    request: RiskPatternsRequest, current_user: User = Depends(get_current_user)
):
    """Выявление паттернов рисков в популяционных данных"""
    try:
        result = await ai_manager.identify_risk_patterns(
            population_data=request.population_data,
            risk_factors=request.risk_factors,
            provider=request.provider,
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка выявления паттернов рисков: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
