"""
Базовый класс для AI провайдеров
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AIRequest(BaseModel):
    """Базовая модель запроса к AI"""

    prompt: str
    max_tokens: int | None = 1000
    temperature: float | None = 0.7
    system_prompt: str | None = None
    context: dict[str, Any] | None = None


class AIResponse(BaseModel):
    """Базовая модель ответа от AI"""

    content: str
    usage: dict[str, int] | None = None
    model: str | None = None
    provider: str
    error: str | None = None


class BaseAIProvider(ABC):
    """Базовый класс для всех AI провайдеров"""

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or self.get_default_model()
        self.provider_name = self.__class__.__name__.replace('Provider', '')

    @abstractmethod
    def get_default_model(self) -> str:
        """Получить модель по умолчанию"""
        pass

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа"""
        pass

    @abstractmethod
    async def analyze_complaint(
        self, complaint: str, patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Анализ жалоб пациента и создание плана обследования"""
        pass

    @abstractmethod
    async def suggest_icd10(
        self, symptoms: list[str], diagnosis: str | None = None
    ) -> list[dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        pass

    @abstractmethod
    async def interpret_lab_results(
        self, results: list[dict[str, Any]], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Интерпретация результатов анализов"""
        pass

    @abstractmethod
    async def analyze_skin(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ состояния кожи по фото"""
        pass

    @abstractmethod
    async def interpret_ecg(
        self, ecg_data: dict[str, Any], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Интерпретация ЭКГ"""
        pass

    def _build_system_prompt(self, role: str) -> str:
        """Построение системного промпта в зависимости от роли"""
        prompts = {
            "doctor": "Вы опытный врач-терапевт с 20-летним стажем. Даете профессиональные медицинские рекомендации.",
            "cardiologist": "Вы врач-кардиолог высшей категории. Специализируетесь на интерпретации ЭКГ и ЭхоКГ.",
            "dermatologist": "Вы врач-дерматолог и косметолог. Анализируете состояние кожи и даете рекомендации.",
            "lab": "Вы врач клинической лабораторной диагностики. Интерпретируете результаты анализов.",
            "icd": "Вы медицинский кодировщик. Помогаете подобрать правильные коды МКБ-10.",
        }
        return prompts.get(role, prompts["doctor"])

    def _format_error(self, error: Exception) -> str:
        """Форматирование ошибки"""
        logger.error(f"{self.provider_name} error: {str(error)}")
        return f"Ошибка {self.provider_name}: {str(error)}"

    @abstractmethod
    async def differential_diagnosis(
        self, symptoms: list[str], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Дифференциальная диагностика на основе симптомов"""
        pass

    @abstractmethod
    async def symptom_analysis(
        self, symptoms: list[str], severity: list[int] | None = None
    ) -> dict[str, Any]:
        """Расширенный анализ симптомов с оценкой тяжести"""
        pass

    @abstractmethod
    async def clinical_decision_support(
        self, case_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Поддержка клинических решений"""
        pass

    @abstractmethod
    async def analyze_xray_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ рентгеновского снимка"""
        pass

    @abstractmethod
    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ УЗИ изображения"""
        pass

    @abstractmethod
    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ дерматоскопического изображения"""
        pass

    @abstractmethod
    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Универсальный анализ медицинского изображения"""
        pass

    @abstractmethod
    async def generate_treatment_plan(
        self,
        patient_data: dict[str, Any],
        diagnosis: str,
        medical_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Генерация персонализированного плана лечения"""
        pass

    @abstractmethod
    async def optimize_medication_regimen(
        self,
        current_medications: list[dict],
        patient_profile: dict[str, Any],
        condition: str,
    ) -> dict[str, Any]:
        """Оптимизация медикаментозной терапии"""
        pass

    @abstractmethod
    async def assess_treatment_effectiveness(
        self, treatment_history: list[dict], patient_response: dict[str, Any]
    ) -> dict[str, Any]:
        """Оценка эффективности лечения"""
        pass

    @abstractmethod
    async def suggest_lifestyle_modifications(
        self, patient_profile: dict[str, Any], conditions: list[str]
    ) -> dict[str, Any]:
        """Рекомендации по изменению образа жизни"""
        pass

    @abstractmethod
    async def check_drug_interactions(
        self,
        medications: list[dict[str, Any]],
        patient_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Проверка лекарственных взаимодействий"""
        pass

    @abstractmethod
    async def analyze_drug_safety(
        self,
        medication: dict[str, Any],
        patient_profile: dict[str, Any],
        conditions: list[str],
    ) -> dict[str, Any]:
        """Анализ безопасности препарата для конкретного пациента"""
        pass

    @abstractmethod
    async def suggest_drug_alternatives(
        self, medication: str, reason: str, patient_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Предложение альтернативных препаратов"""
        pass

    @abstractmethod
    async def calculate_drug_dosage(
        self, medication: str, patient_profile: dict[str, Any], indication: str
    ) -> dict[str, Any]:
        """Расчет дозировки препарата"""
        pass

    @abstractmethod
    async def assess_patient_risk(
        self, patient_data: dict[str, Any], risk_factors: list[str], condition: str
    ) -> dict[str, Any]:
        """Комплексная оценка рисков пациента"""
        pass

    @abstractmethod
    async def predict_complications(
        self,
        patient_profile: dict[str, Any],
        procedure_or_condition: str,
        timeline: str,
    ) -> dict[str, Any]:
        """Прогнозирование возможных осложнений"""
        pass

    @abstractmethod
    async def calculate_mortality_risk(
        self,
        patient_data: dict[str, Any],
        condition: str,
        scoring_system: str | None = None,
    ) -> dict[str, Any]:
        """Расчет риска смертности"""
        pass

    @abstractmethod
    async def assess_surgical_risk(
        self, patient_profile: dict[str, Any], surgery_type: str, anesthesia_type: str
    ) -> dict[str, Any]:
        """Оценка хирургических рисков"""
        pass

    @abstractmethod
    async def predict_readmission_risk(
        self,
        patient_data: dict[str, Any],
        discharge_condition: str,
        social_factors: dict[str, Any],
    ) -> dict[str, Any]:
        """Прогнозирование риска повторной госпитализации"""
        pass

    @abstractmethod
    async def transcribe_audio(
        self, audio_data: bytes, language: str = "ru", medical_context: bool = True
    ) -> dict[str, Any]:
        """Транскрипция аудио в текст с медицинской терминологией"""
        pass

    @abstractmethod
    async def structure_medical_text(
        self, text: str, document_type: str
    ) -> dict[str, Any]:
        """Структурирование медицинского текста в формализованные поля"""
        pass

    @abstractmethod
    async def extract_medical_entities(self, text: str) -> dict[str, Any]:
        """Извлечение медицинских сущностей из текста"""
        pass

    @abstractmethod
    async def generate_medical_summary(
        self, consultation_text: str, patient_history: str | None = None
    ) -> dict[str, Any]:
        """Генерация медицинского резюме из текста консультации"""
        pass

    @abstractmethod
    async def validate_medical_record(
        self, record_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Валидация и проверка медицинской записи на полноту и корректность"""
        pass

    @abstractmethod
    async def optimize_doctor_schedule(
        self, schedule_data: dict[str, Any], constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """Оптимизация расписания врача с учетом ограничений и предпочтений"""
        pass

    @abstractmethod
    async def predict_appointment_duration(
        self, appointment_data: dict[str, Any], historical_data: list[dict]
    ) -> dict[str, Any]:
        """Прогнозирование длительности приема на основе исторических данных"""
        pass

    @abstractmethod
    async def suggest_optimal_slots(
        self,
        doctor_profile: dict[str, Any],
        patient_requirements: dict[str, Any],
        available_slots: list[dict],
    ) -> dict[str, Any]:
        """Предложение оптимальных временных слотов для записи"""
        pass

    @abstractmethod
    async def analyze_workload_distribution(
        self, doctors_data: list[dict], time_period: str
    ) -> dict[str, Any]:
        """Анализ распределения рабочей нагрузки между врачами"""
        pass

    @abstractmethod
    async def generate_shift_recommendations(
        self, department_data: dict[str, Any], staffing_requirements: dict[str, Any]
    ) -> dict[str, Any]:
        """Генерация рекомендаций по составлению смен и графиков работы"""
        pass

    @abstractmethod
    async def analyze_documentation_quality(
        self, medical_records: list[dict], quality_standards: dict[str, Any]
    ) -> dict[str, Any]:
        """Анализ качества медицинской документации"""
        pass

    @abstractmethod
    async def detect_documentation_gaps(
        self, patient_record: dict[str, Any], required_fields: list[str]
    ) -> dict[str, Any]:
        """Выявление пробелов в медицинской документации"""
        pass

    @abstractmethod
    async def suggest_documentation_improvements(
        self, record_analysis: dict[str, Any], best_practices: dict[str, Any]
    ) -> dict[str, Any]:
        """Предложение улучшений для медицинской документации"""
        pass

    @abstractmethod
    async def validate_clinical_consistency(
        self, diagnosis: str, symptoms: list[str], treatment: dict[str, Any]
    ) -> dict[str, Any]:
        """Валидация клинической согласованности диагноза, симптомов и лечения"""
        pass

    @abstractmethod
    async def audit_prescription_safety(
        self, prescriptions: list[dict], patient_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Аудит безопасности назначений и рецептов"""
        pass

    @abstractmethod
    async def analyze_medical_trends(
        self, medical_data: list[dict], time_period: str, analysis_type: str
    ) -> dict[str, Any]:
        """Анализ медицинских трендов и паттернов в данных"""
        pass

    @abstractmethod
    async def detect_anomalies(
        self, dataset: list[dict], baseline_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Выявление аномалий в медицинских данных"""
        pass

    @abstractmethod
    async def predict_outcomes(
        self, patient_data: dict[str, Any], historical_outcomes: list[dict]
    ) -> dict[str, Any]:
        """Прогнозирование медицинских исходов на основе данных"""
        pass

    @abstractmethod
    async def generate_insights_report(
        self, analytics_data: dict[str, Any], report_type: str
    ) -> dict[str, Any]:
        """Генерация отчета с аналитическими инсайтами"""
        pass

    @abstractmethod
    async def identify_risk_patterns(
        self, population_data: list[dict], risk_factors: list[str]
    ) -> dict[str, Any]:
        """Выявление паттернов рисков в популяционных данных"""
        pass

    @abstractmethod
    async def triage_patient(
        self,
        patient_data: dict[str, Any],
        symptoms: list[str],
        vital_signs: dict[str, Any],
    ) -> dict[str, Any]:
        """Триаж пациента с определением уровня срочности и приоритета"""
        pass

    @abstractmethod
    async def assess_emergency_level(
        self, clinical_presentation: dict[str, Any], patient_history: dict[str, Any]
    ) -> dict[str, Any]:
        """Оценка уровня экстренности состояния пациента"""
        pass

    @abstractmethod
    async def prioritize_patient_queue(
        self, patients_queue: list[dict], department_capacity: dict[str, Any]
    ) -> dict[str, Any]:
        """Приоритизация очереди пациентов на основе медицинских показаний"""
        pass

    @abstractmethod
    async def predict_deterioration_risk(
        self, patient_status: dict[str, Any], monitoring_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Прогнозирование риска ухудшения состояния пациента"""
        pass

    @abstractmethod
    async def recommend_care_pathway(
        self, triage_result: dict[str, Any], available_resources: dict[str, Any]
    ) -> dict[str, Any]:
        """Рекомендация маршрута оказания медицинской помощи"""
        pass
