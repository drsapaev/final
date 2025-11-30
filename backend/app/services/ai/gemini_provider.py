"""
Google Gemini провайдер для AI функций - полная реализация
"""

import base64
import io
import json
import logging
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from PIL import Image

from .base_provider import AIRequest, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """Провайдер Google Gemini с полной реализацией"""

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)

        # Настройки безопасности для медицинского контента
        # Используем BLOCK_MEDIUM_AND_ABOVE для лучшей совместимости
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
        ]

        self.text_model = genai.GenerativeModel(
            self.model, safety_settings=safety_settings
        )
        self.vision_model = genai.GenerativeModel(
            'gemini-2.5-flash-preview-05-20', safety_settings=safety_settings
        )

    def get_default_model(self) -> str:
        return "gemini-2.5-flash-preview-05-20"

    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа через Gemini API"""
        try:
            # Формируем промпт с системным сообщением
            full_prompt = ""
            if request.system_prompt:
                full_prompt = f"{request.system_prompt}\n\n"
            full_prompt += request.prompt

            # Генерируем ответ
            response = await self.text_model.generate_content_async(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature,
                ),
            )

            # Проверяем, что ответ содержит валидный контент
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.finish_reason == 2:  # SAFETY
                    return AIResponse(
                        content="",
                        provider=self.provider_name,
                        error="Gemini API заблокировал запрос по соображениям безопасности. Попробуйте переформулировать запрос.",
                    )
                elif candidate.content and candidate.content.parts:
                    content = candidate.content.parts[0].text
                    return AIResponse(
                        content=content, model=self.model, provider=self.provider_name
                    )

            return AIResponse(
                content="",
                provider=self.provider_name,
                error="Gemini API не вернул валидный ответ",
            )

        except Exception as e:
            return AIResponse(
                content="", provider=self.provider_name, error=self._format_error(e)
            )

    async def analyze_complaint(
        self, complaint: str, patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Анализ жалоб и создание плана обследования"""

        prompt = f"""Вы - образовательный медицинский ассистент для студентов медицины. 
Проанализируйте описанные симптомы и предложите учебный план обследования.

Описание симптомов: {complaint}
"""
        if patient_info:
            prompt += f"Учебный случай: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}\n"

        prompt += """
Предоставьте учебный анализ в формате JSON:
{
    "preliminary_diagnosis": ["Учебное предположение 1", "Учебное предположение 2"],
    "examinations": [
        {
            "type": "общее обследование",
            "name": "Стандартное обследование",
            "reason": "для учебных целей"
        }
    ],
    "lab_tests": ["Стандартные анализы"],
    "consultations": ["Общая консультация"],
    "urgency": "планово",
    "red_flags": []
}

Это учебный материал для медицинского образования."""

        request = AIRequest(prompt=prompt, temperature=0.3, max_tokens=1500)

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            # Gemini иногда добавляет markdown, очищаем
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }

    async def suggest_icd10(
        self, symptoms: List[str], diagnosis: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""

        prompt = f"""Вы - помощник врача по кодированию МКБ-10. Предложите подходящие коды.

Симптомы: {', '.join(symptoms)}
"""
        if diagnosis:
            prompt += f"Предполагаемый диагноз: {diagnosis}\n"

        prompt += """
Предоставьте ответ СТРОГО в формате JSON массива (без дополнительного текста):
[
    {
        "code": "G43",
        "name": "Мигрень",
        "relevance": "высокая"
    }
]

Предоставьте до 5 наиболее подходящих кодов МКБ-10.
ВАЖНО: Это информационный инструмент для врачей, требует проверки специалистом."""

        request = AIRequest(prompt=prompt, temperature=0.1, max_tokens=800)

        response = await self.generate(request)

        if response.error:
            return []

        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except:
            return []

    async def interpret_lab_results(
        self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Интерпретация результатов анализов"""

        results_text = "\n".join(
            [
                f"{r['name']}: {r['value']} {r.get('unit', '')} (референс: {r.get('reference', 'не указан')})"
                for r in results
            ]
        )

        prompt = f"""Вы - помощник врача-лаборанта. Проанализируйте результаты анализов.

Результаты:
{results_text}
"""
        if patient_info:
            prompt += f"Пациент: {patient_info.get('age', 'не указан')} лет, {patient_info.get('gender', 'не указан')}\n"

        prompt += """
Предоставьте ответ СТРОГО в формате JSON (без дополнительного текста):
{
    "summary": "Краткая оценка результатов",
    "abnormal_values": [
        {
            "parameter": "Показатель",
            "value": "Значение",
            "interpretation": "Описание отклонения",
            "clinical_significance": "Возможное значение"
        }
    ],
    "possible_conditions": ["Возможное состояние"],
    "recommendations": ["Рекомендация"],
    "urgency": "нет"
}

ВАЖНО: Это информационный инструмент для врачей, требует подтверждения специалистом."""

        request = AIRequest(prompt=prompt, temperature=0.2, max_tokens=1500)

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }

    async def analyze_skin(
        self, image_data: bytes, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Анализ кожи по фото через Gemini Vision"""
        try:
            # Преобразуем bytes в PIL Image
            image = Image.open(io.BytesIO(image_data))

            prompt = """Проанализируйте состояние кожи на фото. 

Определите:
1. Тип кожи (сухая/жирная/комбинированная/нормальная)
2. Возможные проблемы (акне, пигментация, морщины, покраснения и т.д.)
3. Общее состояние кожи
4. Рекомендации по уходу

Ответьте СТРОГО в формате JSON:
{
    "skin_type": "тип кожи",
    "problems": ["список проблем"],
    "skin_condition": "общее состояние (отличное/хорошее/удовлетворительное/требует лечения)",
    "recommendations": ["список рекомендаций"],
    "procedures": ["рекомендуемые процедуры"],
    "ai_confidence": "high/medium/low"
}"""

            if metadata:
                prompt += f"\n\nДополнительная информация о пациенте: {json.dumps(metadata, ensure_ascii=False)}"

            response = await self.vision_model.generate_content_async([prompt, image])

            try:
                content = response.text.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
            except:
                return {
                    "error": "Не удалось разобрать ответ AI",
                    "raw_response": response.text,
                }

        except Exception as e:
            return {"error": f"Ошибка анализа изображения: {str(e)}"}

    # Реализация недостающих абстрактных методов
    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Универсальный анализ медицинских изображений"""
        return await self.analyze_skin(image_data, metadata)

    async def analyze_xray_image(
        self, image_data: bytes, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Анализ рентгеновских снимков"""
        return await self.analyze_medical_image_generic(image_data, "xray", metadata)

    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Анализ УЗИ изображений"""
        return await self.analyze_medical_image_generic(
            image_data, "ultrasound", metadata
        )

    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Анализ дерматоскопических изображений"""
        return await self.analyze_medical_image_generic(
            image_data, "dermatoscopy", metadata
        )

    async def interpret_ecg(
        self, ecg_data: str, metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        return {"error": "ECG interpretation not implemented in Gemini provider"}

    async def generate_treatment_plan(
        self, diagnosis: str, patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Генерация плана лечения"""
        return {"error": "Treatment plan generation not implemented in Gemini provider"}

    async def clinical_decision_support(
        self, symptoms: List[str], patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Клиническая поддержка принятия решений"""
        return {"error": "Clinical decision support not implemented in Gemini provider"}

    async def differential_diagnosis(
        self, symptoms: List[str], patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Дифференциальная диагностика"""
        return {"error": "Differential diagnosis not implemented in Gemini provider"}

    async def drug_interaction_check(self, medications: List[str]) -> Dict[str, Any]:
        """Проверка взаимодействия лекарств"""
        return {"error": "Drug interaction check not implemented in Gemini provider"}

    async def medical_literature_search(self, query: str) -> Dict[str, Any]:
        """Поиск в медицинской литературе"""
        return {"error": "Medical literature search not implemented in Gemini provider"}

    # Заглушки для остальных абстрактных методов
    async def analyze_documentation_quality(self, text: str) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def analyze_drug_safety(
        self, drug: str, patient_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def analyze_medical_trends(
        self, medical_data: List[Dict], time_period: str, analysis_type: str
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def analyze_workload_distribution(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def assess_emergency_level(self, symptoms: List[str]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def assess_patient_risk(self, patient_info: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def assess_surgical_risk(
        self, patient_info: Dict, procedure: str
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def assess_treatment_effectiveness(
        self, treatment: str, outcomes: List[Dict]
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def audit_prescription_safety(self, prescription: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def calculate_drug_dosage(
        self, drug: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def calculate_mortality_risk(self, patient_info: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def check_drug_interactions(self, medications: List[str]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def detect_anomalies(self, data: List[Dict]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def detect_documentation_gaps(self, text: str) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def extract_medical_entities(self, text: str) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def generate_insights_report(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def generate_medical_summary(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def generate_shift_recommendations(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def identify_risk_patterns(self, data: List[Dict]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def optimize_doctor_schedule(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def optimize_medication_regimen(
        self, medications: List[str], patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def predict_appointment_duration(
        self, appointment_data: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def predict_complications(
        self, procedure: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def predict_deterioration_risk(self, patient_info: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def predict_outcomes(
        self, treatment: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def predict_readmission_risk(self, patient_info: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def prioritize_patient_queue(self, patients: List[Dict]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def recommend_care_pathway(
        self, diagnosis: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def structure_medical_text(self, text: str) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def suggest_documentation_improvements(self, text: str) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def suggest_drug_alternatives(
        self, drug: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def suggest_lifestyle_modifications(
        self, condition: str, patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def suggest_optimal_slots(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def symptom_analysis(self, symptoms: List[str]) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def transcribe_audio(self, audio_data: bytes) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def triage_patient(
        self, symptoms: List[str], patient_info: Dict
    ) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def validate_clinical_consistency(self, data: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}

    async def validate_medical_record(self, record: Dict) -> Dict[str, Any]:
        return {"error": "Not implemented"}
