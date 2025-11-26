"""
Google Gemini провайдер для AI функций
"""
from typing import Dict, List, Optional, Any
import google.generativeai as genai
import json
import base64
from PIL import Image
import io
from .base_provider import BaseAIProvider, AIRequest, AIResponse
import logging

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """Провайдер Google Gemini"""
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        self.text_model = genai.GenerativeModel(self.model)
        self.vision_model = genai.GenerativeModel('gemini-pro-vision')
    
    def get_default_model(self) -> str:
        return "gemini-pro"
    
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
                    temperature=request.temperature
                )
            )
            
            return AIResponse(
                content=response.text,
                model=self.model,
                provider=self.provider_name
            )
        except Exception as e:
            return AIResponse(
                content="",
                provider=self.provider_name,
                error=self._format_error(e)
            )
    
    async def analyze_complaint(self, complaint: str, patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ жалоб и создание плана обследования"""
        system_prompt = self._build_system_prompt("doctor")
        
        prompt = f"""{system_prompt}

Проанализируйте жалобы пациента и составьте план обследования.

Жалобы: {complaint}
"""
        if patient_info:
            prompt += f"\nИнформация о пациенте: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}"
        
        prompt += """

Ответьте СТРОГО в формате JSON без дополнительного текста:
{
    "preliminary_diagnosis": ["список предварительных диагнозов"],
    "examinations": [
        {
            "type": "тип обследования",
            "name": "название",
            "reason": "обоснование"
        }
    ],
    "lab_tests": ["список анализов"],
    "consultations": ["список консультаций специалистов"],
    "urgency": "срочность (экстренно/планово/неотложно)",
    "red_flags": ["тревожные симптомы, если есть"]
}"""
        
        request = AIRequest(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500
        )
        
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
                "raw_response": response.content
            }
    
    async def suggest_icd10(self, symptoms: List[str], diagnosis: Optional[str] = None) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        system_prompt = self._build_system_prompt("icd")
        
        prompt = f"""{system_prompt}

Подберите коды МКБ-10 для следующих симптомов и диагноза.

Симптомы: {', '.join(symptoms)}
"""
        if diagnosis:
            prompt += f"\nДиагноз: {diagnosis}"
        
        prompt += """

Верните ТОЛЬКО JSON массив без дополнительного текста:
[
    {
        "code": "код МКБ-10",
        "name": "название диагноза",
        "relevance": "высокая/средняя/низкая"
    }
]

Верните не более 5 наиболее релевантных кодов."""
        
        request = AIRequest(
            prompt=prompt,
            temperature=0.1,
            max_tokens=800
        )
        
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
    
    async def interpret_lab_results(self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация результатов анализов"""
        system_prompt = self._build_system_prompt("lab")
        
        results_text = "\n".join([
            f"{r['name']}: {r['value']} {r.get('unit', '')} (норма: {r.get('reference', 'не указана')})"
            for r in results
        ])
        
        prompt = f"""{system_prompt}

Проинтерпретируйте результаты лабораторных анализов.

Результаты:
{results_text}
"""
        if patient_info:
            prompt += f"\nПациент: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}"
        
        prompt += """

Ответьте СТРОГО в формате JSON:
{
    "summary": "общее заключение",
    "abnormal_values": [
        {
            "parameter": "название параметра",
            "value": "значение",
            "interpretation": "интерпретация отклонения",
            "clinical_significance": "клиническое значение"
        }
    ],
    "possible_conditions": ["возможные состояния/заболевания"],
    "recommendations": ["рекомендации по дообследованию"],
    "urgency": "требуется ли срочная консультация (да/нет)"
}"""
        
        request = AIRequest(
            prompt=prompt,
            temperature=0.2,
            max_tokens=1500
        )
        
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
                "raw_response": response.content
            }
    
    async def analyze_skin(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
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
            
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
            
        except Exception as e:
            return {"error": self._format_error(e)}
    
    async def interpret_ecg(self, ecg_data: Dict[str, Any], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        system_prompt = self._build_system_prompt("cardiologist")
        
        ecg_params = ecg_data.get('parameters', {})
        
        prompt = f"""{system_prompt}

Проинтерпретируйте данные ЭКГ.

Параметры ЭКГ:
- ЧСС: {ecg_params.get('heart_rate', 'не указано')} уд/мин
- Интервал PQ: {ecg_params.get('pq_interval', 'не указано')} мс
- Комплекс QRS: {ecg_params.get('qrs_duration', 'не указано')} мс
- Интервал QT: {ecg_params.get('qt_interval', 'не указано')} мс
- QTc: {ecg_params.get('qtc', 'не указано')} мс
- Ось сердца: {ecg_params.get('axis', 'не указано')}°
"""
        
        if patient_info:
            prompt += f"\nПациент: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}"
        
        if ecg_data.get('auto_interpretation'):
            prompt += f"\nАвтоматическая интерпретация аппарата: {ecg_data['auto_interpretation']}"
        
        prompt += """

Ответьте СТРОГО в формате JSON:
{
    "rhythm": "характеристика ритма",
    "rate": "оценка ЧСС",
    "conduction": "проводимость",
    "axis": "электрическая ось сердца",
    "abnormalities": ["список выявленных отклонений"],
    "interpretation": "общее заключение",
    "recommendations": ["рекомендации"],
    "urgency": "срочность консультации кардиолога (экстренно/планово/не требуется)"
}"""
        
        request = AIRequest(
            prompt=prompt,
            temperature=0.2,
            max_tokens=1200
        )
        
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
                "raw_response": response.content
            }
