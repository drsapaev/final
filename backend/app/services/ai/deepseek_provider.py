"""
DeepSeek провайдер для AI функций
"""
from typing import Dict, List, Optional, Any
import httpx
import json
import base64
from .base_provider import BaseAIProvider, AIRequest, AIResponse
import logging

logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseAIProvider):
    """Провайдер DeepSeek (экономичная альтернатива)"""
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model)
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_default_model(self) -> str:
        return "deepseek-chat"
    
    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа через DeepSeek API"""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
            
            return AIResponse(
                content=data["choices"][0]["message"]["content"],
                usage=data.get("usage"),
                model=data.get("model", self.model),
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
        system_prompt = self._build_system_prompt("doctor") + "\nВсегда отвечайте на русском языке."
        
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
            # DeepSeek обычно возвращает чистый JSON
            return json.loads(response.content)
        except:
            # Пробуем извлечь JSON из текста
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
    
    async def suggest_icd10(self, symptoms: List[str], diagnosis: Optional[str] = None) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        system_prompt = self._build_system_prompt("icd") + "\nВсегда отвечайте на русском языке."
        
        prompt = f"""Подберите коды МКБ-10 для следующих симптомов и диагноза.

Симптомы: {', '.join(symptoms)}
"""
        if diagnosis:
            prompt += f"\nДиагноз: {diagnosis}"
        
        prompt += """

Верните список наиболее подходящих кодов МКБ-10 в формате JSON массива:
[
    {
        "code": "код МКБ-10",
        "name": "название диагноза на русском",
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
            # Пробуем извлечь JSON массив
            import re
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            return []
    
    async def interpret_lab_results(self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация результатов анализов"""
        system_prompt = self._build_system_prompt("lab") + "\nВсегда отвечайте на русском языке."
        
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
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
    
    async def analyze_skin(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ кожи по фото"""
        # DeepSeek пока не поддерживает анализ изображений напрямую
        # Используем текстовое описание если оно есть в metadata
        if metadata and metadata.get('description'):
            system_prompt = self._build_system_prompt("dermatologist") + "\nВсегда отвечайте на русском языке."
            
            prompt = f"""На основе описания состояния кожи пациента, проведите анализ.

Описание: {metadata['description']}
"""
            if metadata.get('age'):
                prompt += f"\nВозраст пациента: {metadata['age']}"
            if metadata.get('skin_concerns'):
                prompt += f"\nЖалобы: {', '.join(metadata['skin_concerns'])}"
            
            prompt += """

Ответьте в формате JSON:
{
    "skin_type": "тип кожи (сухая/жирная/комбинированная/нормальная)",
    "problems": ["список выявленных проблем"],
    "skin_condition": "общее состояние (отличное/хорошее/удовлетворительное/требует лечения)",
    "recommendations": ["список рекомендаций по уходу"],
    "procedures": ["рекомендуемые косметологические процедуры"],
    "ai_confidence": "medium"
}"""
            
            request = AIRequest(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            response = await self.generate(request)
            
            if response.error:
                return {"error": response.error}
            
            try:
                result = json.loads(response.content)
                result["note"] = "Анализ выполнен на основе текстового описания"
                return result
            except:
                return {
                    "error": "Не удалось разобрать ответ AI",
                    "raw_response": response.content
                }
        else:
            return {
                "error": "DeepSeek не поддерживает прямой анализ изображений. Предоставьте текстовое описание в metadata.",
                "supported": False
            }
    
    async def interpret_ecg(self, ecg_data: Dict[str, Any], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        system_prompt = self._build_system_prompt("cardiologist") + "\nВсегда отвечайте на русском языке."
        
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
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content
            }
