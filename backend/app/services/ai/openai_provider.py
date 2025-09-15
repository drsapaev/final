"""
OpenAI провайдер для AI функций
"""
from typing import Dict, List, Optional, Any
import openai
from openai import AsyncOpenAI
import json
import base64
from .base_provider import BaseAIProvider, AIRequest, AIResponse
import logging

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """Провайдер OpenAI (GPT-4, GPT-3.5)"""
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model)
        self.client = AsyncOpenAI(api_key=api_key)
    
    def get_default_model(self) -> str:
        return "gpt-4-turbo-preview"
    
    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа через OpenAI API"""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            return AIResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                model=response.model,
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
        
        prompt = f"""Проанализируйте жалобы пациента и составьте план обследования.

Жалобы: {complaint}
"""
        if patient_info:
            prompt += f"\nИнформация о пациенте: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}"
        
        prompt += """

Ответьте в формате JSON:
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
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )
        
        response = await self.generate(request)
        
        if response.error:
            return {"error": response.error}
        
        try:
            return json.loads(response.content)
        except:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
    
    async def suggest_icd10(self, symptoms: List[str], diagnosis: Optional[str] = None) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        system_prompt = self._build_system_prompt("icd")
        
        prompt = f"""Подберите коды МКБ-10 для следующих симптомов и диагноза.

Симптомы: {', '.join(symptoms)}
"""
        if diagnosis:
            prompt += f"\nДиагноз: {diagnosis}"
        
        prompt += """

Верните список наиболее подходящих кодов МКБ-10 в формате JSON:
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
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=800
        )
        
        response = await self.generate(request)
        
        if response.error:
            return []
        
        try:
            return json.loads(response.content)
        except:
            return []
    
    async def interpret_lab_results(self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация результатов анализов"""
        system_prompt = self._build_system_prompt("lab")
        
        results_text = "\n".join([
            f"{r['name']}: {r['value']} {r.get('unit', '')} (норма: {r.get('reference', 'не указана')})"
            for r in results
        ])
        
        prompt = f"""Проинтерпретируйте результаты лабораторных анализов.

Результаты:
{results_text}
"""
        if patient_info:
            prompt += f"\nПациент: возраст {patient_info.get('age', 'не указан')}, пол {patient_info.get('gender', 'не указан')}"
        
        prompt += """

Ответьте в формате JSON:
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
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=1500
        )
        
        response = await self.generate(request)
        
        if response.error:
            return {"error": response.error}
        
        try:
            return json.loads(response.content)
        except:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
    
    async def analyze_skin(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ кожи по фото через GPT-4 Vision"""
        try:
            # Кодируем изображение в base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            system_prompt = self._build_system_prompt("dermatologist")
            
            user_content = [
                {
                    "type": "text",
                    "text": "Проанализируйте состояние кожи на фото. Определите тип кожи, возможные проблемы и дайте рекомендации."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
            
            if metadata:
                user_content[0]["text"] += f"\n\nДополнительная информация: {json.dumps(metadata, ensure_ascii=False)}"
            
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            
            # Пытаемся извлечь JSON из ответа
            try:
                # Ищем JSON в ответе
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    # Если JSON не найден, возвращаем структурированный ответ
                    return {
                        "skin_type": "не определен",
                        "problems": ["требуется ручной анализ"],
                        "recommendations": [content],
                        "ai_confidence": "low"
                    }
            except:
                return {
                    "analysis": content,
                    "structured": False
                }
                
        except Exception as e:
            return {"error": self._format_error(e)}
    
    async def interpret_ecg(self, ecg_data: Dict[str, Any], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        system_prompt = self._build_system_prompt("cardiologist")
        
        ecg_params = ecg_data.get('parameters', {})
        
        prompt = f"""Проинтерпретируйте данные ЭКГ.

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
            prompt += f"\nАвтоматическая интерпретация: {ecg_data['auto_interpretation']}"
        
        prompt += """

Ответьте в формате JSON:
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
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=1200
        )
        
        response = await self.generate(request)
        
        if response.error:
            return {"error": response.error}
        
        try:
            return json.loads(response.content)
        except:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
