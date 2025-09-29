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
    
    async def differential_diagnosis(self, symptoms: List[str], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Дифференциальная диагностика на основе симптомов"""
        age = patient_info.get("age", "не указан") if patient_info else "не указан"
        gender = patient_info.get("gender", "не указан") if patient_info else "не указан"
        
        symptoms_text = ", ".join(symptoms)
        
        prompt = f"""
        Проведите дифференциальную диагностику для пациента со следующими симптомами:
        
        Симптомы: {symptoms_text}
        Возраст: {age}
        Пол: {gender}
        
        Предоставьте:
        1. Список наиболее вероятных диагнозов (с вероятностью в %)
        2. Дополнительные вопросы для уточнения диагноза
        3. Рекомендуемые обследования
        4. Красные флаги (симптомы, требующие немедленного внимания)
        
        Ответ в формате JSON:
        {{
            "differential_diagnoses": [
                {{
                    "diagnosis": "название диагноза",
                    "probability": 85,
                    "icd10_code": "код МКБ-10",
                    "reasoning": "обоснование"
                }}
            ],
            "clarifying_questions": ["вопрос 1", "вопрос 2"],
            "recommended_tests": ["обследование 1", "обследование 2"],
            "red_flags": ["красный флаг 1", "красный флаг 2"],
            "urgency_level": "низкий/средний/высокий/критический"
        }}
        """
        
        system_prompt = """Вы опытный врач-диагност с 25-летним стажем. 
        Специализируетесь на дифференциальной диагностике. 
        Всегда учитываете возраст и пол пациента при постановке диагноза.
        Ответы даете только в формате JSON."""
        
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
    
    async def symptom_analysis(self, symptoms: List[str], severity: Optional[List[int]] = None) -> Dict[str, Any]:
        """Расширенный анализ симптомов с оценкой тяжести"""
        symptoms_with_severity = []
        
        for i, symptom in enumerate(symptoms):
            severity_score = severity[i] if severity and i < len(severity) else None
            if severity_score:
                symptoms_with_severity.append(f"{symptom} (тяжесть: {severity_score}/10)")
            else:
                symptoms_with_severity.append(symptom)
        
        symptoms_text = "\n".join([f"- {s}" for s in symptoms_with_severity])
        
        prompt = f"""
        Проанализируйте следующие симптомы:
        
        {symptoms_text}
        
        Предоставьте:
        1. Группировку симптомов по системам органов
        2. Анализ взаимосвязей между симптомами
        3. Оценку общей тяжести состояния
        4. Возможные синдромы
        5. Рекомендации по приоритетности обследования
        
        Ответ в формате JSON:
        {{
            "symptom_groups": {{
                "cardiovascular": ["симптом1", "симптом2"],
                "respiratory": ["симптом3"],
                "neurological": ["симптом4"]
            }},
            "symptom_relationships": [
                {{
                    "symptoms": ["симптом1", "симптом2"],
                    "relationship": "описание связи"
                }}
            ],
            "severity_assessment": {{
                "overall_score": 7,
                "description": "умеренно тяжелое состояние",
                "most_concerning": ["самый тревожный симптом"]
            }},
            "possible_syndromes": ["синдром 1", "синдром 2"],
            "examination_priority": ["первоочередное", "второстепенное"]
        }}
        """
        
        system_prompt = """Вы врач-терапевт с экспертизой в симптоматологии. 
        Анализируете симптомы системно, учитывая их взаимосвязи и клиническое значение.
        Ответы даете только в формате JSON."""
        
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
    
    async def clinical_decision_support(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Поддержка клинических решений"""
        prompt = f"""
        Проанализируйте клинический случай и предоставьте рекомендации:
        
        Данные пациента: {json.dumps(case_data, ensure_ascii=False, indent=2)}
        
        Предоставьте:
        1. Анализ представленных данных
        2. Наиболее вероятный диагноз
        3. План дальнейшего обследования
        4. Рекомендации по лечению
        5. Прогноз
        6. Критерии для направления к специалисту
        
        Ответ в формате JSON:
        {{
            "data_analysis": "анализ представленных данных",
            "primary_diagnosis": {{
                "diagnosis": "основной диагноз",
                "confidence": 85,
                "icd10_code": "код МКБ-10"
            }},
            "investigation_plan": [
                {{
                    "test": "название обследования",
                    "priority": "высокий/средний/низкий",
                    "rationale": "обоснование"
                }}
            ],
            "treatment_recommendations": [
                {{
                    "intervention": "вмешательство",
                    "details": "детали",
                    "monitoring": "что контролировать"
                }}
            ],
            "prognosis": {{
                "short_term": "краткосрочный прогноз",
                "long_term": "долгосрочный прогноз"
            }},
            "referral_criteria": ["критерий 1", "критерий 2"]
        }}
        """
        
        system_prompt = """Вы опытный врач-консультант с экспертизой в клинической медицине. 
        Предоставляете комплексные рекомендации по ведению пациентов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
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
    
    async def differential_diagnosis(self, symptoms: List[str], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Дифференциальная диагностика на основе симптомов"""
        age = patient_info.get("age", "не указан") if patient_info else "не указан"
        gender = patient_info.get("gender", "не указан") if patient_info else "не указан"
        
        symptoms_text = ", ".join(symptoms)
        
        prompt = f"""
        Проведите дифференциальную диагностику для пациента со следующими симптомами:
        
        Симптомы: {symptoms_text}
        Возраст: {age}
        Пол: {gender}
        
        Предоставьте:
        1. Список наиболее вероятных диагнозов (с вероятностью в %)
        2. Дополнительные вопросы для уточнения диагноза
        3. Рекомендуемые обследования
        4. Красные флаги (симптомы, требующие немедленного внимания)
        
        Ответ в формате JSON:
        {{
            "differential_diagnoses": [
                {{
                    "diagnosis": "название диагноза",
                    "probability": 85,
                    "icd10_code": "код МКБ-10",
                    "reasoning": "обоснование"
                }}
            ],
            "clarifying_questions": ["вопрос 1", "вопрос 2"],
            "recommended_tests": ["обследование 1", "обследование 2"],
            "red_flags": ["красный флаг 1", "красный флаг 2"],
            "urgency_level": "низкий/средний/высокий/критический"
        }}
        """
        
        system_prompt = """Вы опытный врач-диагност с 25-летним стажем. 
        Специализируетесь на дифференциальной диагностике. 
        Всегда учитываете возраст и пол пациента при постановке диагноза.
        Ответы даете только в формате JSON."""
        
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
    
    async def symptom_analysis(self, symptoms: List[str], severity: Optional[List[int]] = None) -> Dict[str, Any]:
        """Расширенный анализ симптомов с оценкой тяжести"""
        symptoms_with_severity = []
        
        for i, symptom in enumerate(symptoms):
            severity_score = severity[i] if severity and i < len(severity) else None
            if severity_score:
                symptoms_with_severity.append(f"{symptom} (тяжесть: {severity_score}/10)")
            else:
                symptoms_with_severity.append(symptom)
        
        symptoms_text = "\n".join([f"- {s}" for s in symptoms_with_severity])
        
        prompt = f"""
        Проанализируйте следующие симптомы:
        
        {symptoms_text}
        
        Предоставьте:
        1. Группировку симптомов по системам органов
        2. Анализ взаимосвязей между симптомами
        3. Оценку общей тяжести состояния
        4. Возможные синдромы
        5. Рекомендации по приоритетности обследования
        
        Ответ в формате JSON:
        {{
            "symptom_groups": {{
                "cardiovascular": ["симптом1", "симптом2"],
                "respiratory": ["симптом3"],
                "neurological": ["симптом4"]
            }},
            "symptom_relationships": [
                {{
                    "symptoms": ["симптом1", "симптом2"],
                    "relationship": "описание связи"
                }}
            ],
            "severity_assessment": {{
                "overall_score": 7,
                "description": "умеренно тяжелое состояние",
                "most_concerning": ["самый тревожный симптом"]
            }},
            "possible_syndromes": ["синдром 1", "синдром 2"],
            "examination_priority": ["первоочередное", "второстепенное"]
        }}
        """
        
        system_prompt = """Вы врач-терапевт с экспертизой в симптоматологии. 
        Анализируете симптомы системно, учитывая их взаимосвязи и клиническое значение.
        Ответы даете только в формате JSON."""
        
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
    
    async def clinical_decision_support(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Поддержка клинических решений"""
        prompt = f"""
        Проанализируйте клинический случай и предоставьте рекомендации:
        
        Данные пациента: {json.dumps(case_data, ensure_ascii=False, indent=2)}
        
        Предоставьте:
        1. Анализ представленных данных
        2. Наиболее вероятный диагноз
        3. План дальнейшего обследования
        4. Рекомендации по лечению
        5. Прогноз
        6. Критерии для направления к специалисту
        
        Ответ в формате JSON:
        {{
            "data_analysis": "анализ представленных данных",
            "primary_diagnosis": {{
                "diagnosis": "основной диагноз",
                "confidence": 85,
                "icd10_code": "код МКБ-10"
            }},
            "investigation_plan": [
                {{
                    "test": "название обследования",
                    "priority": "высокий/средний/низкий",
                    "rationale": "обоснование"
                }}
            ],
            "treatment_recommendations": [
                {{
                    "intervention": "вмешательство",
                    "details": "детали",
                    "monitoring": "что контролировать"
                }}
            ],
            "prognosis": {{
                "short_term": "краткосрочный прогноз",
                "long_term": "долгосрочный прогноз"
            }},
            "referral_criteria": ["критерий 1", "критерий 2"]
        }}
        """
        
        system_prompt = """Вы опытный врач-консультант с экспертизой в клинической медицине. 
        Предоставляете комплексные рекомендации по ведению пациентов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
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
    
    async def differential_diagnosis(self, symptoms: List[str], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Дифференциальная диагностика на основе симптомов"""
        age = patient_info.get("age", "не указан") if patient_info else "не указан"
        gender = patient_info.get("gender", "не указан") if patient_info else "не указан"
        
        symptoms_text = ", ".join(symptoms)
        
        prompt = f"""
        Проведите дифференциальную диагностику для пациента со следующими симптомами:
        
        Симптомы: {symptoms_text}
        Возраст: {age}
        Пол: {gender}
        
        Предоставьте:
        1. Список наиболее вероятных диагнозов (с вероятностью в %)
        2. Дополнительные вопросы для уточнения диагноза
        3. Рекомендуемые обследования
        4. Красные флаги (симптомы, требующие немедленного внимания)
        
        Ответ в формате JSON:
        {{
            "differential_diagnoses": [
                {{
                    "diagnosis": "название диагноза",
                    "probability": 85,
                    "icd10_code": "код МКБ-10",
                    "reasoning": "обоснование"
                }}
            ],
            "clarifying_questions": ["вопрос 1", "вопрос 2"],
            "recommended_tests": ["обследование 1", "обследование 2"],
            "red_flags": ["красный флаг 1", "красный флаг 2"],
            "urgency_level": "низкий/средний/высокий/критический"
        }}
        """
        
        system_prompt = """Вы опытный врач-диагност с 25-летним стажем. 
        Специализируетесь на дифференциальной диагностике. 
        Всегда учитываете возраст и пол пациента при постановке диагноза.
        Ответы даете только в формате JSON."""
        
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
    
    async def symptom_analysis(self, symptoms: List[str], severity: Optional[List[int]] = None) -> Dict[str, Any]:
        """Расширенный анализ симптомов с оценкой тяжести"""
        symptoms_with_severity = []
        
        for i, symptom in enumerate(symptoms):
            severity_score = severity[i] if severity and i < len(severity) else None
            if severity_score:
                symptoms_with_severity.append(f"{symptom} (тяжесть: {severity_score}/10)")
            else:
                symptoms_with_severity.append(symptom)
        
        symptoms_text = "\n".join([f"- {s}" for s in symptoms_with_severity])
        
        prompt = f"""
        Проанализируйте следующие симптомы:
        
        {symptoms_text}
        
        Предоставьте:
        1. Группировку симптомов по системам органов
        2. Анализ взаимосвязей между симптомами
        3. Оценку общей тяжести состояния
        4. Возможные синдромы
        5. Рекомендации по приоритетности обследования
        
        Ответ в формате JSON:
        {{
            "symptom_groups": {{
                "cardiovascular": ["симптом1", "симптом2"],
                "respiratory": ["симптом3"],
                "neurological": ["симптом4"]
            }},
            "symptom_relationships": [
                {{
                    "symptoms": ["симптом1", "симптом2"],
                    "relationship": "описание связи"
                }}
            ],
            "severity_assessment": {{
                "overall_score": 7,
                "description": "умеренно тяжелое состояние",
                "most_concerning": ["самый тревожный симптом"]
            }},
            "possible_syndromes": ["синдром 1", "синдром 2"],
            "examination_priority": ["первоочередное", "второстепенное"]
        }}
        """
        
        system_prompt = """Вы врач-терапевт с экспертизой в симптоматологии. 
        Анализируете симптомы системно, учитывая их взаимосвязи и клиническое значение.
        Ответы даете только в формате JSON."""
        
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
    
    async def clinical_decision_support(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Поддержка клинических решений"""
        prompt = f"""
        Проанализируйте клинический случай и предоставьте рекомендации:
        
        Данные пациента: {json.dumps(case_data, ensure_ascii=False, indent=2)}
        
        Предоставьте:
        1. Анализ представленных данных
        2. Наиболее вероятный диагноз
        3. План дальнейшего обследования
        4. Рекомендации по лечению
        5. Прогноз
        6. Критерии для направления к специалисту
        
        Ответ в формате JSON:
        {{
            "data_analysis": "анализ представленных данных",
            "primary_diagnosis": {{
                "diagnosis": "основной диагноз",
                "confidence": 85,
                "icd10_code": "код МКБ-10"
            }},
            "investigation_plan": [
                {{
                    "test": "название обследования",
                    "priority": "высокий/средний/низкий",
                    "rationale": "обоснование"
                }}
            ],
            "treatment_recommendations": [
                {{
                    "intervention": "вмешательство",
                    "details": "детали",
                    "monitoring": "что контролировать"
                }}
            ],
            "prognosis": {{
                "short_term": "краткосрочный прогноз",
                "long_term": "долгосрочный прогноз"
            }},
            "referral_criteria": ["критерий 1", "критерий 2"]
        }}
        """
        
        system_prompt = """Вы опытный врач-консультант с экспертизой в клинической медицине. 
        Предоставляете комплексные рекомендации по ведению пациентов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
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


    # Новые методы для анализа медицинских изображений
    async def analyze_xray_image(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ рентгеновского снимка"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        body_part = metadata.get("body_part", "не указано") if metadata else "не указано"
        patient_age = metadata.get("patient_age", "не указан") if metadata else "не указан"
        clinical_info = metadata.get("clinical_info", "") if metadata else ""
        
        prompt = f"""Проанализируйте рентгеновский снимок как опытный врач-рентгенолог.
        
        Область исследования: {body_part}
        Возраст пациента: {patient_age}
        Клиническая информация: {clinical_info}
        
        Предоставьте анализ в формате JSON с техническим качеством, анатомическими структурами, патологическими находками и рекомендациями."""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": "Вы опытный врач-рентгенолог. Анализируете снимки с высокой точностью. Ответы только в формате JSON."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}
    
    async def analyze_ultrasound_image(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ УЗИ изображения"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        organ = metadata.get("organ", "не указан") if metadata else "не указан"
        patient_age = metadata.get("patient_age", "не указан") if metadata else "не указан"
        
        prompt = f"""Проанализируйте ультразвуковое изображение как врач УЗИ-диагностики.
        
        Исследуемый орган: {organ}
        Возраст пациента: {patient_age}
        
        Предоставьте анализ в формате JSON с качеством изображения, анатомической оценкой, патологическими изменениями и рекомендациями."""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": "Вы опытный врач УЗИ-диагностики. Анализируете изображения с учетом технических параметров. Ответы только в формате JSON."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}
    
    async def analyze_dermatoscopy_image(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ дерматоскопического изображения"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        lesion_location = metadata.get("lesion_location", "не указана") if metadata else "не указана"
        patient_age = metadata.get("patient_age", "не указан") if metadata else "не указан"
        
        prompt = f"""Проанализируйте дерматоскопическое изображение как дерматолог-онколог.
        
        Локализация образования: {lesion_location}
        Возраст пациента: {patient_age}
        
        Проведите анализ по системе ABCDE и предоставьте результат в формате JSON с дерматоскопическими признаками, оценкой риска, дифференциальной диагностикой и рекомендациями."""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": "Вы опытный дерматолог-онколог с экспертизой в дерматоскопии. Анализируете по стандартам ABCDE. Ответы только в формате JSON."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=2500,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}
    
    async def analyze_medical_image_generic(self, image_data: bytes, image_type: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Универсальный анализ медицинского изображения"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        patient_info = ""
        if metadata:
            patient_info = f"Возраст: {metadata.get('patient_age', 'не указан')}, Пол: {metadata.get('patient_gender', 'не указан')}"
        
        prompt = f"""Проанализируйте медицинское изображение типа {image_type} как врач-специалист.
        
        {patient_info}
        
        Предоставьте профессиональный анализ в формате JSON с качеством изображения, патологическими находками, нормальными структурами, дифференциальной диагностикой и рекомендациями."""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": f"Вы опытный врач-специалист по анализу медицинских изображений типа {image_type}. Ответы только в формате JSON."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}

    async def generate_treatment_plan(self, patient_data: Dict[str, Any], diagnosis: str, medical_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Генерация персонализированного плана лечения"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        weight = patient_data.get("weight", "не указан")
        allergies = patient_data.get("allergies", [])
        comorbidities = patient_data.get("comorbidities", [])
        
        history_text = ""
        if medical_history:
            history_text = "\n".join([
                f"- {h.get('date', 'дата не указана')}: {h.get('diagnosis', 'диагноз не указан')} - {h.get('treatment', 'лечение не указано')}"
                for h in medical_history
            ])
        
        prompt = f"""
        Создайте персонализированный план лечения для пациента:
        
        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        - Сопутствующие заболевания: {', '.join(comorbidities) if comorbidities else 'не указаны'}
        
        ТЕКУЩИЙ ДИАГНОЗ: {diagnosis}
        
        МЕДИЦИНСКАЯ ИСТОРИЯ:
        {history_text if history_text else 'История отсутствует'}
        
        Предоставьте комплексный план лечения в формате JSON с целями лечения, медикаментозной терапией, немедикаментозными вмешательствами, рекомендациями по образу жизни и графиком наблюдения.
        """
        
        system_prompt = """Вы опытный врач-клиницист с экспертизой в персонализированной медицине.
        Создаете индивидуальные планы лечения с учетом всех особенностей пациента.
        Всегда учитываете возраст, пол, сопутствующие заболевания, аллергии и историю болезни.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=2500
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
    
    async def optimize_medication_regimen(self, current_medications: List[Dict], patient_profile: Dict[str, Any], condition: str) -> Dict[str, Any]:
        """Оптимизация медикаментозной терапии"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])
        
        medications_text = "\n".join([
            f"- {med.get('name', 'не указано')}: {med.get('dosage', 'не указано')} {med.get('frequency', 'не указано')}"
            for med in current_medications
        ])
        
        prompt = f"""
        Оптимизируйте медикаментозную терапию для пациента:
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        
        СОСТОЯНИЕ: {condition}
        
        ТЕКУЩИЕ ПРЕПАРАТЫ:
        {medications_text}
        
        Предоставьте оптимизированный план в формате JSON с изменениями препаратов, анализом взаимодействий и рекомендациями по мониторингу.
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в оптимизации лекарственной терапии.
        Анализируете взаимодействия препаратов, корректируете дозировки с учетом функции органов.
        Всегда учитываете безопасность, эффективность и приверженность лечению.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2000
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
    
    async def assess_treatment_effectiveness(self, treatment_history: List[Dict], patient_response: Dict[str, Any]) -> Dict[str, Any]:
        """Оценка эффективности лечения"""
        history_text = "\n".join([
            f"- {h.get('date', 'дата не указана')}: {h.get('treatment', 'лечение не указано')} - {h.get('outcome', 'результат не указан')}"
            for h in treatment_history
        ])
        
        current_symptoms = patient_response.get("symptoms", [])
        side_effects = patient_response.get("side_effects", [])
        quality_of_life = patient_response.get("quality_of_life_score", "не указан")
        adherence = patient_response.get("adherence_rate", "не указан")
        
        prompt = f"""
        Оцените эффективность проводимого лечения:
        
        ИСТОРИЯ ЛЕЧЕНИЯ:
        {history_text}
        
        ТЕКУЩИЙ ОТВЕТ ПАЦИЕНТА:
        - Симптомы: {', '.join(current_symptoms) if current_symptoms else 'отсутствуют'}
        - Побочные эффекты: {', '.join(side_effects) if side_effects else 'отсутствуют'}
        - Качество жизни (1-10): {quality_of_life}
        - Приверженность лечению (%): {adherence}
        
        Предоставьте анализ эффективности в формате JSON с оценкой ответа на лечение, анализом побочных эффектов и рекомендациями по корректировке.
        """
        
        system_prompt = """Вы опытный врач-клиницист с экспертизой в оценке эффективности лечения.
        Анализируете динамику состояния пациента, приверженность терапии и качество жизни.
        Даете объективную оценку и конкретные рекомендации по корректировке лечения.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=2000
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
    
    async def suggest_lifestyle_modifications(self, patient_profile: Dict[str, Any], conditions: List[str]) -> Dict[str, Any]:
        """Рекомендации по изменению образа жизни"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        bmi = patient_profile.get("bmi", "не указан")
        activity_level = patient_profile.get("activity_level", "не указан")
        smoking_status = patient_profile.get("smoking_status", "не указан")
        alcohol_consumption = patient_profile.get("alcohol_consumption", "не указано")
        occupation = patient_profile.get("occupation", "не указана")
        
        conditions_text = ", ".join(conditions) if conditions else "не указаны"
        
        prompt = f"""
        Разработайте персонализированные рекомендации по изменению образа жизни:
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - ИМТ: {bmi}
        - Уровень активности: {activity_level}
        - Курение: {smoking_status}
        - Употребление алкоголя: {alcohol_consumption}
        - Профессия: {occupation}
        
        СОСТОЯНИЯ: {conditions_text}
        
        Предоставьте рекомендации в формате JSON с диетическими рекомендациями, физической активностью, управлением стрессом и модификацией привычек.
        """
        
        system_prompt = """Вы специалист по профилактической медицине и здоровому образу жизни.
        Создаете персонализированные, реалистичные и научно обоснованные рекомендации.
        Учитываете индивидуальные особенности пациента и его заболевания.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=2500
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

    async def check_drug_interactions(self, medications: List[Dict[str, Any]], patient_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Проверка лекарственных взаимодействий"""
        medications_text = "\n".join([
            f"- {med.get('name', 'не указано')}: {med.get('dosage', 'не указано')} {med.get('frequency', 'не указано')}"
            for med in medications
        ])
        
        patient_info = ""
        if patient_profile:
            age = patient_profile.get("age", "не указан")
            gender = patient_profile.get("gender", "не указан")
            weight = patient_profile.get("weight", "не указан")
            kidney_function = patient_profile.get("kidney_function", "не указана")
            liver_function = patient_profile.get("liver_function", "не указана")
            allergies = patient_profile.get("allergies", [])
            
            patient_info = f"""
            ПРОФИЛЬ ПАЦИЕНТА:
            - Возраст: {age}
            - Пол: {gender}
            - Вес: {weight}
            - Функция почек: {kidney_function}
            - Функция печени: {liver_function}
            - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
            """
        
        prompt = f"""
        Проанализируйте лекарственные взаимодействия между препаратами:
        
        ПРЕПАРАТЫ:
        {medications_text}
        {patient_info}
        
        Предоставьте детальный анализ в формате JSON:
        {{
            "interaction_summary": {{
                "total_interactions": "количество найденных взаимодействий",
                "severity_distribution": {{
                    "critical": 0,
                    "major": 0,
                    "moderate": 0,
                    "minor": 0
                }},
                "overall_risk": "низкий/умеренный/высокий/критический"
            }},
            "interactions": [
                {{
                    "drug_1": "название первого препарата",
                    "drug_2": "название второго препарата",
                    "interaction_type": "фармакокинетическое/фармакодинамическое/физико-химическое",
                    "mechanism": "механизм взаимодействия",
                    "severity": "критическое/значительное/умеренное/незначительное",
                    "clinical_effect": "клинический эффект взаимодействия",
                    "onset": "быстрое/отсроченное/неопределенное",
                    "documentation": "хорошо документировано/умеренно/слабо",
                    "management": "рекомендации по управлению взаимодействием",
                    "monitoring": "что контролировать"
                }}
            ],
            "contraindications": [
                {{
                    "medication": "название препарата",
                    "contraindication": "противопоказание",
                    "reason": "причина противопоказания",
                    "severity": "абсолютное/относительное"
                }}
            ],
            "dosage_adjustments": [
                {{
                    "medication": "название препарата",
                    "current_dose": "текущая доза",
                    "recommended_dose": "рекомендуемая доза",
                    "reason": "причина корректировки",
                    "monitoring_required": "необходимый мониторинг"
                }}
            ],
            "timing_recommendations": [
                {{
                    "medications": ["препарат 1", "препарат 2"],
                    "recommendation": "рекомендация по времени приема",
                    "interval": "интервал между приемами",
                    "rationale": "обоснование"
                }}
            ],
            "alternative_suggestions": [
                {{
                    "problematic_drug": "проблемный препарат",
                    "alternatives": ["альтернатива 1", "альтернатива 2"],
                    "rationale": "обоснование замены"
                }}
            ],
            "monitoring_plan": {{
                "laboratory_tests": ["анализ 1", "анализ 2"],
                "clinical_parameters": ["параметр 1", "параметр 2"],
                "frequency": "частота контроля",
                "warning_signs": ["признак 1", "признак 2"]
            }},
            "patient_education": [
                "важная информация для пациента 1",
                "важная информация для пациента 2"
            ]
        }}
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в лекарственных взаимодействиях.
        Анализируете взаимодействия препаратов на основе современных клинических данных.
        Учитываете фармакокинетику, фармакодинамику и индивидуальные особенности пациента.
        Предоставляете практические рекомендации по безопасному применению препаратов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3000
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
    
    async def analyze_drug_safety(self, medication: Dict[str, Any], patient_profile: Dict[str, Any], conditions: List[str]) -> Dict[str, Any]:
        """Анализ безопасности препарата для конкретного пациента"""
        med_name = medication.get("name", "не указано")
        med_dosage = medication.get("dosage", "не указано")
        med_frequency = medication.get("frequency", "не указано")
        
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        pregnancy_status = patient_profile.get("pregnancy_status", "не указан")
        breastfeeding = patient_profile.get("breastfeeding", "не указано")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])
        
        conditions_text = ", ".join(conditions) if conditions else "не указаны"
        
        prompt = f"""
        Проанализируйте безопасность препарата для конкретного пациента:
        
        ПРЕПАРАТ:
        - Название: {med_name}
        - Дозировка: {med_dosage}
        - Частота: {med_frequency}
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Беременность: {pregnancy_status}
        - Грудное вскармливание: {breastfeeding}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        
        ЗАБОЛЕВАНИЯ: {conditions_text}
        
        Предоставьте анализ безопасности в формате JSON:
        {{
            "safety_assessment": {{
                "overall_safety": "безопасно/осторожно/не рекомендуется/противопоказано",
                "risk_level": "низкий/умеренный/высокий/критический",
                "confidence": "высокая/средняя/низкая"
            }},
            "contraindications": {{
                "absolute": ["абсолютное противопоказание 1"],
                "relative": ["относительное противопоказание 1"],
                "patient_specific": ["специфичное для пациента противопоказание 1"]
            }},
            "age_considerations": {{
                "appropriate_for_age": true/false,
                "age_specific_risks": ["риск 1", "риск 2"],
                "dosage_adjustment_needed": true/false,
                "adjustment_rationale": "обоснование корректировки дозы"
            }},
            "organ_function_impact": {{
                "kidney": {{
                    "clearance_affected": true/false,
                    "adjustment_needed": true/false,
                    "recommendation": "рекомендация"
                }},
                "liver": {{
                    "metabolism_affected": true/false,
                    "adjustment_needed": true/false,
                    "recommendation": "рекомендация"
                }}
            }},
            "special_populations": {{
                "pregnancy": {{
                    "category": "A/B/C/D/X",
                    "safety": "безопасно/осторожно/не рекомендуется/противопоказано",
                    "considerations": "особые соображения"
                }},
                "breastfeeding": {{
                    "compatible": true/false,
                    "considerations": "особые соображения"
                }}
            }},
            "monitoring_requirements": {{
                "laboratory_monitoring": ["анализ 1", "анализ 2"],
                "clinical_monitoring": ["параметр 1", "параметр 2"],
                "frequency": "частота контроля",
                "baseline_tests": ["базовый тест 1", "базовый тест 2"]
            }},
            "adverse_effects": {{
                "common": ["частый побочный эффект 1"],
                "serious": ["серьезный побочный эффект 1"],
                "patient_specific_risks": ["специфичный риск 1"]
            }},
            "drug_allergy_risk": {{
                "cross_reactivity": ["препарат с перекрестной реактивностью"],
                "allergy_risk": "низкий/умеренный/высокий",
                "precautions": ["предосторожность 1"]
            }},
            "recommendations": {{
                "proceed": true/false,
                "modifications": ["модификация 1", "модификация 2"],
                "alternatives": ["альтернатива 1", "альтернатива 2"],
                "patient_counseling": ["совет пациенту 1", "совет пациенту 2"]
            }}
        }}
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в безопасности лекарственных средств.
        Оцениваете безопасность препаратов с учетом индивидуальных особенностей пациента.
        Учитываете возраст, пол, функцию органов, сопутствующие заболевания и аллергии.
        Предоставляете практические рекомендации по безопасному применению.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2500
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
    
    async def suggest_drug_alternatives(self, medication: str, reason: str, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Предложение альтернативных препаратов"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])
        conditions = patient_profile.get("conditions", [])
        
        prompt = f"""
        Предложите альтернативные препараты для замены:
        
        ПРЕПАРАТ ДЛЯ ЗАМЕНЫ: {medication}
        ПРИЧИНА ЗАМЕНЫ: {reason}
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        - Заболевания: {', '.join(conditions) if conditions else 'не указаны'}
        
        Предоставьте альтернативы в формате JSON:
        {{
            "original_medication": {{
                "name": "{medication}",
                "replacement_reason": "{reason}",
                "therapeutic_class": "терапевтический класс"
            }},
            "alternatives": [
                {{
                    "medication_name": "название альтернативного препарата",
                    "generic_name": "международное название",
                    "therapeutic_class": "терапевтический класс",
                    "mechanism_of_action": "механизм действия",
                    "advantages": ["преимущество 1", "преимущество 2"],
                    "disadvantages": ["недостаток 1", "недостаток 2"],
                    "dosage_forms": ["форма выпуска 1", "форма выпуска 2"],
                    "typical_dosage": "типичная дозировка",
                    "administration": "способ применения",
                    "contraindications": ["противопоказание 1", "противопоказание 2"],
                    "side_effects": ["побочный эффект 1", "побочный эффект 2"],
                    "drug_interactions": ["взаимодействие 1", "взаимодействие 2"],
                    "monitoring_required": ["что контролировать 1", "что контролировать 2"],
                    "cost_consideration": "экономические соображения",
                    "availability": "доступность",
                    "patient_suitability": {{
                        "age_appropriate": true/false,
                        "renal_safe": true/false,
                        "hepatic_safe": true/false,
                        "allergy_safe": true/false,
                        "condition_appropriate": true/false
                    }},
                    "recommendation_strength": "сильная/умеренная/слабая",
                    "evidence_level": "высокий/средний/низкий"
                }}
            ],
            "comparison_table": {{
                "efficacy": {{
                    "original": "эффективность оригинального препарата",
                    "alternatives": ["эффективность альтернативы 1", "эффективность альтернативы 2"]
                }},
                "safety": {{
                    "original": "безопасность оригинального препарата",
                    "alternatives": ["безопасность альтернативы 1", "безопасность альтернативы 2"]
                }},
                "cost": {{
                    "original": "стоимость оригинального препарата",
                    "alternatives": ["стоимость альтернативы 1", "стоимость альтернативы 2"]
                }}
            }},
            "transition_plan": {{
                "washout_period": "период отмены",
                "titration_schedule": "схема титрования",
                "monitoring_during_transition": ["что контролировать при переходе"],
                "patient_education": ["что объяснить пациенту"]
            }},
            "final_recommendation": {{
                "preferred_alternative": "предпочтительная альтернатива",
                "rationale": "обоснование выбора",
                "implementation_priority": "высокий/средний/низкий"
            }}
        }}
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в подборе альтернативных препаратов.
        Предлагаете безопасные и эффективные альтернативы с учетом индивидуальных особенностей пациента.
        Учитываете эффективность, безопасность, стоимость и доступность препаратов.
        Предоставляете практические рекомендации по переходу на альтернативную терапию.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3500
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
    
    async def calculate_drug_dosage(self, medication: str, patient_profile: Dict[str, Any], indication: str) -> Dict[str, Any]:
        """Расчет дозировки препарата"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        height = patient_profile.get("height", "не указан")
        bsa = patient_profile.get("body_surface_area", "не указана")
        creatinine = patient_profile.get("creatinine", "не указан")
        creatinine_clearance = patient_profile.get("creatinine_clearance", "не указан")
        liver_function = patient_profile.get("liver_function", "не указана")
        
        prompt = f"""
        Рассчитайте оптимальную дозировку препарата для пациента:
        
        ПРЕПАРАТ: {medication}
        ПОКАЗАНИЕ: {indication}
        
        ПАРАМЕТРЫ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - Площадь поверхности тела: {bsa} м²
        - Креатинин: {creatinine} мкмоль/л
        - Клиренс креатинина: {creatinine_clearance} мл/мин
        - Функция печени: {liver_function}
        
        Предоставьте расчет дозировки в формате JSON:
        {{
            "medication_info": {{
                "name": "{medication}",
                "indication": "{indication}",
                "therapeutic_class": "терапевтический класс",
                "dosing_method": "по весу/по площади поверхности/фиксированная доза"
            }},
            "standard_dosing": {{
                "adult_dose": "стандартная доза для взрослых",
                "pediatric_dose": "детская доза (если применимо)",
                "elderly_dose": "доза для пожилых",
                "dose_range": "диапазон доз",
                "maximum_dose": "максимальная доза"
            }},
            "calculated_dose": {{
                "recommended_dose": "рекомендуемая доза для пациента",
                "calculation_method": "метод расчета",
                "calculation_details": "детали расчета",
                "dose_per_kg": "доза на кг веса",
                "dose_per_m2": "доза на м² поверхности тела (если применимо)"
            }},
            "dosing_schedule": {{
                "frequency": "частота приема",
                "interval": "интервал между приемами",
                "duration": "продолжительность курса",
                "timing_with_meals": "связь с приемом пищи",
                "special_instructions": ["особые указания"]
            }},
            "organ_function_adjustments": {{
                "renal_adjustment": {{
                    "needed": true/false,
                    "adjusted_dose": "скорректированная доза",
                    "rationale": "обоснование корректировки",
                    "monitoring": "необходимый мониторинг"
                }},
                "hepatic_adjustment": {{
                    "needed": true/false,
                    "adjusted_dose": "скорректированная доза",
                    "rationale": "обоснование корректировки",
                    "monitoring": "необходимый мониторинг"
                }}
            }},
            "age_specific_considerations": {{
                "pediatric_considerations": "особенности для детей",
                "elderly_considerations": "особенности для пожилых",
                "dose_adjustment_rationale": "обоснование возрастной корректировки"
            }},
            "titration_plan": {{
                "starting_dose": "начальная доза",
                "titration_schedule": "схема титрования",
                "target_dose": "целевая доза",
                "titration_parameters": "параметры для титрования",
                "stopping_criteria": "критерии прекращения титрования"
            }},
            "monitoring_plan": {{
                "therapeutic_monitoring": "терапевтический мониторинг",
                "safety_monitoring": "мониторинг безопасности",
                "laboratory_tests": ["лабораторный тест 1", "лабораторный тест 2"],
                "clinical_parameters": ["клинический параметр 1", "клинический параметр 2"],
                "monitoring_frequency": "частота мониторинга"
            }},
            "dose_modifications": {{
                "efficacy_insufficient": "корректировка при недостаточной эффективности",
                "adverse_effects": "корректировка при побочных эффектах",
                "drug_interactions": "корректировка при взаимодействиях",
                "missed_dose_instructions": "инструкции при пропуске дозы"
            }},
            "patient_counseling": {{
                "administration_instructions": ["инструкция по применению 1"],
                "storage_instructions": "условия хранения",
                "warning_signs": ["тревожный признак 1", "тревожный признак 2"],
                "lifestyle_modifications": ["модификация образа жизни 1"]
            }}
        }}
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в расчете дозировок лекарственных средств.
        Рассчитываете индивидуальные дозировки с учетом возраста, веса, функции органов и показаний.
        Учитываете фармакокинетику, фармакодинамику и индивидуальную вариабельность.
        Предоставляете практические рекомендации по дозированию и мониторингу.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3000
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

    async def assess_patient_risk(self, patient_data: Dict[str, Any], risk_factors: List[str], condition: str) -> Dict[str, Any]:
        """Комплексная оценка рисков пациента"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        weight = patient_data.get("weight", "не указан")
        height = patient_data.get("height", "не указан")
        bmi = patient_data.get("bmi", "не указан")
        smoking_status = patient_data.get("smoking_status", "не указан")
        alcohol_consumption = patient_data.get("alcohol_consumption", "не указано")
        comorbidities = patient_data.get("comorbidities", [])
        medications = patient_data.get("medications", [])
        family_history = patient_data.get("family_history", [])
        
        risk_factors_text = ", ".join(risk_factors) if risk_factors else "не указаны"
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = ", ".join([med.get("name", "не указано") for med in medications]) if medications else "не указаны"
        family_history_text = ", ".join(family_history) if family_history else "не указан"
        
        prompt = f"""
        Проведите комплексную оценку рисков для пациента:
        
        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - ИМТ: {bmi}
        - Курение: {smoking_status}
        - Употребление алкоголя: {alcohol_consumption}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Семейный анамнез: {family_history_text}
        
        СОСТОЯНИЕ/ЗАБОЛЕВАНИЕ: {condition}
        ФАКТОРЫ РИСКА: {risk_factors_text}
        
        Предоставьте детальную оценку рисков в формате JSON:
        {{
            "overall_risk_assessment": {{
                "risk_level": "низкий/умеренный/высокий/критический",
                "risk_score": "числовая оценка от 1 до 100",
                "confidence_level": "высокая/средняя/низкая",
                "assessment_date": "дата оценки"
            }},
            "risk_categories": {{
                "cardiovascular_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "10_year_risk": "процент риска на 10 лет"
                }},
                "metabolic_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "diabetes_risk": "процент риска развития диабета"
                }},
                "oncological_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "screening_recommendations": ["рекомендация 1", "рекомендация 2"]
                }},
                "infectious_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "vaccination_status": "актуальность вакцинации"
                }}
            }},
            "modifiable_risk_factors": [
                {{
                    "factor": "название фактора",
                    "current_status": "текущее состояние",
                    "target_value": "целевое значение",
                    "intervention": "рекомендуемое вмешательство",
                    "potential_risk_reduction": "потенциальное снижение риска в %"
                }}
            ],
            "non_modifiable_risk_factors": [
                {{
                    "factor": "название фактора",
                    "impact": "влияние на общий риск",
                    "management_strategy": "стратегия управления"
                }}
            ],
            "risk_stratification": {{
                "primary_prevention": {{
                    "applicable": true/false,
                    "recommendations": ["рекомендация 1", "рекомендация 2"],
                    "timeline": "временные рамки"
                }},
                "secondary_prevention": {{
                    "applicable": true/false,
                    "recommendations": ["рекомендация 1", "рекомендация 2"],
                    "timeline": "временные рамки"
                }}
            }},
            "monitoring_plan": {{
                "frequency": "частота наблюдения",
                "parameters": ["параметр 1", "параметр 2"],
                "laboratory_tests": ["анализ 1", "анализ 2"],
                "imaging_studies": ["исследование 1", "исследование 2"],
                "specialist_referrals": ["специалист 1", "специалист 2"]
            }},
            "risk_communication": {{
                "patient_friendly_explanation": "объяснение для пациента",
                "visual_aids": ["тип визуализации 1", "тип визуализации 2"],
                "key_messages": ["ключевое сообщение 1", "ключевое сообщение 2"]
            }},
            "emergency_indicators": [
                {{
                    "indicator": "тревожный признак",
                    "action": "необходимые действия",
                    "urgency": "немедленно/в течение часа/в течение дня"
                }}
            ]
        }}
        """
        
        system_prompt = """Вы врач-эпидемиолог и специалист по оценке рисков с экспертизой в профилактической медицине.
        Проводите комплексную оценку рисков на основе современных клинических рекомендаций и доказательной медицины.
        Учитываете все факторы риска, их взаимодействие и кумулятивный эффект.
        Предоставляете практические рекомендации по снижению рисков и мониторингу.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3500
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
    
    async def predict_complications(self, patient_profile: Dict[str, Any], procedure_or_condition: str, timeline: str) -> Dict[str, Any]:
        """Прогнозирование возможных осложнений"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        comorbidities = patient_profile.get("comorbidities", [])
        medications = patient_profile.get("medications", [])
        allergies = patient_profile.get("allergies", [])
        previous_complications = patient_profile.get("previous_complications", [])
        
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = ", ".join([med.get("name", "не указано") for med in medications]) if medications else "не указаны"
        allergies_text = ", ".join(allergies) if allergies else "не указаны"
        complications_text = ", ".join(previous_complications) if previous_complications else "не указаны"
        
        prompt = f"""
        Спрогнозируйте возможные осложнения для пациента:
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Аллергии: {allergies_text}
        - Предыдущие осложнения: {complications_text}
        
        ПРОЦЕДУРА/СОСТОЯНИЕ: {procedure_or_condition}
        ВРЕМЕННЫЕ РАМКИ: {timeline}
        
        Предоставьте прогноз осложнений в формате JSON:
        {{
            "complication_overview": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "total_complications_predicted": "количество возможных осложнений",
                "timeline_analysis": "анализ временных рамок",
                "confidence_level": "высокая/средняя/низкая"
            }},
            "immediate_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "early_signs": ["ранний признак 1", "ранний признак 2"],
                    "prevention_strategies": ["стратегия профилактики 1", "стратегия профилактики 2"],
                    "management_approach": "подход к лечению"
                }}
            ],
            "short_term_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "intervention_threshold": "пороговые значения для вмешательства"
                }}
            ],
            "long_term_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "screening_recommendations": ["рекомендация по скринингу 1", "рекомендация по скринингу 2"],
                    "long_term_monitoring": "долгосрочное наблюдение"
                }}
            ],
            "system_specific_risks": {{
                "cardiovascular": ["риск 1", "риск 2"],
                "respiratory": ["риск 1", "риск 2"],
                "neurological": ["риск 1", "риск 2"],
                "gastrointestinal": ["риск 1", "риск 2"],
                "renal": ["риск 1", "риск 2"],
                "infectious": ["риск 1", "риск 2"]
            }},
            "patient_specific_factors": {{
                "age_related_risks": ["возрастной риск 1", "возрастной риск 2"],
                "gender_specific_risks": ["гендерный риск 1", "гендерный риск 2"],
                "comorbidity_interactions": ["взаимодействие 1", "взаимодействие 2"],
                "medication_related_risks": ["лекарственный риск 1", "лекарственный риск 2"]
            }},
            "prevention_protocol": {{
                "pre_procedure_measures": ["мера 1", "мера 2"],
                "intra_procedure_precautions": ["предосторожность 1", "предосторожность 2"],
                "post_procedure_monitoring": ["мониторинг 1", "мониторинг 2"],
                "patient_education": ["образование 1", "образование 2"]
            }},
            "emergency_preparedness": {{
                "high_risk_scenarios": ["сценарий 1", "сценарий 2"],
                "emergency_protocols": ["протокол 1", "протокол 2"],
                "required_resources": ["ресурс 1", "ресурс 2"],
                "escalation_criteria": ["критерий эскалации 1", "критерий эскалации 2"]
            }}
        }}
        """
        
        system_prompt = """Вы опытный врач-клиницист с экспертизой в прогнозировании и профилактике осложнений.
        Анализируете риски на основе современных клинических данных и доказательной медицины.
        Учитываете индивидуальные особенности пациента и специфику процедуры/состояния.
        Предоставляете практические рекомендации по профилактике и раннему выявлению осложнений.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4000
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
    
    async def calculate_mortality_risk(self, patient_data: Dict[str, Any], condition: str, scoring_system: Optional[str] = None) -> Dict[str, Any]:
        """Расчет риска смертности"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        vital_signs = patient_data.get("vital_signs", {})
        laboratory_values = patient_data.get("laboratory_values", {})
        comorbidities = patient_data.get("comorbidities", [])
        severity_indicators = patient_data.get("severity_indicators", {})
        
        vital_signs_text = ", ".join([f"{k}: {v}" for k, v in vital_signs.items()]) if vital_signs else "не указаны"
        lab_values_text = ", ".join([f"{k}: {v}" for k, v in laboratory_values.items()]) if laboratory_values else "не указаны"
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        severity_text = ", ".join([f"{k}: {v}" for k, v in severity_indicators.items()]) if severity_indicators else "не указаны"
        
        scoring_system_info = f"Используйте шкалу: {scoring_system}" if scoring_system else "Используйте наиболее подходящую валидированную шкалу"
        
        prompt = f"""
        Рассчитайте риск смертности для пациента:
        
        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Витальные показатели: {vital_signs_text}
        - Лабораторные показатели: {lab_values_text}
        - Сопутствующие заболевания: {comorbidities_text}
        - Показатели тяжести: {severity_text}
        
        СОСТОЯНИЕ: {condition}
        СИСТЕМА ОЦЕНКИ: {scoring_system_info}
        
        Предоставьте расчет риска смертности в формате JSON:
        {{
            "mortality_assessment": {{
                "primary_scoring_system": "название используемой шкалы",
                "total_score": "общий балл по шкале",
                "risk_category": "низкий/умеренный/высокий/критический",
                "predicted_mortality": {{
                    "in_hospital": "процент внутрибольничной смертности",
                    "30_day": "процент 30-дневной смертности",
                    "90_day": "процент 90-дневной смертности",
                    "1_year": "процент годовой смертности"
                }},
                "confidence_interval": "доверительный интервал",
                "calibration_note": "примечание о калибровке шкалы"
            }},
            "scoring_breakdown": {{
                "age_points": "баллы за возраст",
                "gender_points": "баллы за пол",
                "comorbidity_points": "баллы за сопутствующие заболевания",
                "vital_signs_points": "баллы за витальные показатели",
                "laboratory_points": "баллы за лабораторные показатели",
                "severity_points": "баллы за тяжесть состояния"
            }},
            "risk_factors_analysis": {{
                "major_risk_factors": [
                    {{
                        "factor": "название фактора",
                        "contribution": "вклад в общий риск",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "protective_factors": [
                    {{
                        "factor": "название защитного фактора",
                        "benefit": "защитный эффект",
                        "enhancement_potential": "потенциал для усиления"
                    }}
                ]
            }},
            "alternative_scores": [
                {{
                    "scoring_system": "альтернативная шкала",
                    "score": "балл",
                    "predicted_mortality": "прогнозируемая смертность",
                    "applicability": "применимость к данному случаю"
                }}
            ],
            "clinical_interpretation": {{
                "risk_level_description": "описание уровня риска",
                "clinical_implications": "клинические последствия",
                "treatment_intensity": "рекомендуемая интенсивность лечения",
                "monitoring_frequency": "частота мониторинга"
            }},
            "interventions_by_risk": {{
                "immediate_interventions": ["немедленное вмешательство 1", "немедленное вмешательство 2"],
                "short_term_goals": ["краткосрочная цель 1", "краткосрочная цель 2"],
                "long_term_strategies": ["долгосрочная стратегия 1", "долгосрочная стратегия 2"]
            }},
            "prognostic_indicators": {{
                "favorable_indicators": ["благоприятный показатель 1", "благоприятный показатель 2"],
                "unfavorable_indicators": ["неблагоприятный показатель 1", "неблагоприятный показатель 2"],
                "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
            }},
            "family_communication": {{
                "risk_explanation": "объяснение риска для семьи",
                "prognosis_discussion": "обсуждение прогноза",
                "decision_support": "поддержка в принятии решений"
            }}
        }}
        """
        
        system_prompt = """Вы врач-реаниматолог и специалист по интенсивной терапии с экспертизой в оценке тяжести состояния.
        Используете валидированные шкалы оценки риска смертности (APACHE, SOFA, SAPS, CHA2DS2-VASc и др.).
        Интерпретируете результаты в клиническом контексте и предоставляете практические рекомендации.
        Учитываете ограничения шкал и индивидуальные особенности пациента.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3500
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
    
    async def assess_surgical_risk(self, patient_profile: Dict[str, Any], surgery_type: str, anesthesia_type: str) -> Dict[str, Any]:
        """Оценка хирургических рисков"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        height = patient_profile.get("height", "не указан")
        asa_class = patient_profile.get("asa_class", "не указан")
        comorbidities = patient_profile.get("comorbidities", [])
        medications = patient_profile.get("medications", [])
        previous_surgeries = patient_profile.get("previous_surgeries", [])
        allergies = patient_profile.get("allergies", [])
        functional_status = patient_profile.get("functional_status", "не указан")
        
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = ", ".join([med.get("name", "не указано") for med in medications]) if medications else "не указаны"
        surgeries_text = ", ".join(previous_surgeries) if previous_surgeries else "не указаны"
        allergies_text = ", ".join(allergies) if allergies else "не указаны"
        
        prompt = f"""
        Оцените хирургические риски для пациента:
        
        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - Класс ASA: {asa_class}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Предыдущие операции: {surgeries_text}
        - Аллергии: {allergies_text}
        - Функциональный статус: {functional_status}
        
        ТИП ОПЕРАЦИИ: {surgery_type}
        ТИП АНЕСТЕЗИИ: {anesthesia_type}
        
        Предоставьте оценку хирургических рисков в формате JSON:
        {{
            "surgical_risk_assessment": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "asa_classification": "класс ASA с обоснованием",
                "predicted_mortality": "прогнозируемая смертность в %",
                "predicted_morbidity": "прогнозируемая заболеваемость в %",
                "risk_stratification": "стратификация риска"
            }},
            "perioperative_risks": {{
                "preoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "mitigation_strategies": ["стратегия 1", "стратегия 2"]
                    }}
                ],
                "intraoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "prevention_measures": ["мера 1", "мера 2"]
                    }}
                ],
                "postoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "monitoring_requirements": ["требование 1", "требование 2"]
                    }}
                ]
            }},
            "anesthesia_considerations": {{
                "anesthesia_risk": "низкий/умеренный/высокий/критический",
                "specific_concerns": ["проблема 1", "проблема 2"],
                "airway_assessment": "оценка дыхательных путей",
                "cardiovascular_considerations": "сердечно-сосудистые соображения",
                "drug_interactions": ["взаимодействие 1", "взаимодействие 2"],
                "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"]
            }},
            "procedure_specific_risks": {{
                "technical_complexity": "низкая/умеренная/высокая/критическая",
                "duration_considerations": "соображения по продолжительности",
                "positioning_risks": ["риск позиционирования 1", "риск позиционирования 2"],
                "blood_loss_risk": "риск кровопотери",
                "infection_risk": "риск инфекции",
                "organ_specific_risks": ["органоспецифичный риск 1", "органоспецифичный риск 2"]
            }},
            "optimization_recommendations": {{
                "preoperative_optimization": [
                    {{
                        "intervention": "вмешательство",
                        "timeline": "временные рамки",
                        "expected_benefit": "ожидаемая польза",
                        "monitoring_parameters": ["параметр 1", "параметр 2"]
                    }}
                ],
                "medication_adjustments": [
                    {{
                        "medication": "препарат",
                        "adjustment": "корректировка",
                        "rationale": "обоснование",
                        "timing": "время выполнения"
                    }}
                ]
            }},
            "postoperative_care_plan": {{
                "monitoring_level": "уровень мониторинга (палата/ПИТ/ОРИТ)",
                "duration_of_monitoring": "продолжительность мониторинга",
                "key_parameters": ["ключевой параметр 1", "ключевой параметр 2"],
                "early_mobilization": "план ранней мобилизации",
                "pain_management": "план обезболивания",
                "discharge_criteria": ["критерий выписки 1", "критерий выписки 2"]
            }},
            "alternative_approaches": [
                {{
                    "approach": "альтернативный подход",
                    "risk_benefit_ratio": "соотношение риск/польза",
                    "suitability": "подходящность для пациента",
                    "considerations": ["соображение 1", "соображение 2"]
                }}
            ],
            "informed_consent_points": [
                "ключевой пункт для информированного согласия 1",
                "ключевой пункт для информированного согласия 2"
            ]
        }}
        """
        
        system_prompt = """Вы анестезиолог-реаниматолог с экспертизой в периоперационной медицине.
        Оцениваете хирургические риски на основе современных клинических рекомендаций и валидированных шкал.
        Учитываете все аспекты периоперационного периода и индивидуальные особенности пациента.
        Предоставляете практические рекомендации по оптимизации и минимизации рисков.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4000
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
    
    async def predict_readmission_risk(self, patient_data: Dict[str, Any], discharge_condition: str, social_factors: Dict[str, Any]) -> Dict[str, Any]:
        """Прогнозирование риска повторной госпитализации"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        primary_diagnosis = patient_data.get("primary_diagnosis", "не указан")
        comorbidities = patient_data.get("comorbidities", [])
        medications = patient_data.get("medications", [])
        length_of_stay = patient_data.get("length_of_stay", "не указана")
        previous_admissions = patient_data.get("previous_admissions", "не указаны")
        
        social_support = social_factors.get("social_support", "не указана")
        insurance_status = social_factors.get("insurance_status", "не указан")
        transportation = social_factors.get("transportation", "не указан")
        housing_situation = social_factors.get("housing_situation", "не указана")
        caregiver_availability = social_factors.get("caregiver_availability", "не указана")
        health_literacy = social_factors.get("health_literacy", "не указана")
        
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = ", ".join([med.get("name", "не указано") for med in medications]) if medications else "не указаны"
        
        prompt = f"""
        Спрогнозируйте риск повторной госпитализации для пациента:
        
        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Основной диагноз: {primary_diagnosis}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Длительность госпитализации: {length_of_stay}
        - Предыдущие госпитализации: {previous_admissions}
        
        СОСТОЯНИЕ ПРИ ВЫПИСКЕ: {discharge_condition}
        
        СОЦИАЛЬНЫЕ ФАКТОРЫ:
        - Социальная поддержка: {social_support}
        - Страховой статус: {insurance_status}
        - Транспорт: {transportation}
        - Жилищные условия: {housing_situation}
        - Доступность ухода: {caregiver_availability}
        - Медицинская грамотность: {health_literacy}
        
        Предоставьте прогноз риска повторной госпитализации в формате JSON:
        {{
            "readmission_risk_assessment": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "risk_score": "числовая оценка от 1 до 100",
                "predicted_readmission_rates": {{
                    "7_day": "процент 7-дневной реадмиссии",
                    "30_day": "процент 30-дневной реадмиссии",
                    "90_day": "процент 90-дневной реадмиссии",
                    "1_year": "процент годовой реадмиссии"
                }},
                "confidence_level": "высокая/средняя/низкая"
            }},
            "risk_factor_analysis": {{
                "medical_risk_factors": [
                    {{
                        "factor": "медицинский фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "social_risk_factors": [
                    {{
                        "factor": "социальный фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "system_risk_factors": [
                    {{
                        "factor": "системный фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ]
            }},
            "high_risk_scenarios": [
                {{
                    "scenario": "сценарий высокого риска",
                    "probability": "вероятность в %",
                    "timeline": "временные рамки",
                    "warning_signs": ["предупреждающий признак 1", "предупреждающий признак 2"],
                    "prevention_strategies": ["стратегия профилактики 1", "стратегия профилактики 2"]
                }}
            ],
            "discharge_planning_recommendations": {{
                "medication_reconciliation": {{
                    "priority": "высокий/средний/низкий",
                    "specific_actions": ["действие 1", "действие 2"],
                    "follow_up_required": true/false
                }},
                "follow_up_appointments": {{
                    "primary_care": "рекомендации по первичной помощи",
                    "specialist_care": "рекомендации по специализированной помощи",
                    "timeline": "временные рамки для записи",
                    "priority_level": "высокий/средний/низкий"
                }},
                "patient_education": {{
                    "key_topics": ["ключевая тема 1", "ключевая тема 2"],
                    "education_methods": ["метод обучения 1", "метод обучения 2"],
                    "comprehension_assessment": "оценка понимания"
                }}
            }},
            "care_coordination": {{
                "care_team_members": ["член команды 1", "член команды 2"],
                "communication_plan": "план коммуникации",
                "care_transitions": ["переход 1", "переход 2"],
                "monitoring_responsibilities": ["ответственность за мониторинг 1", "ответственность за мониторинг 2"]
            }},
            "intervention_strategies": {{
                "high_intensity_interventions": [
                    {{
                        "intervention": "интенсивное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ],
                "moderate_intensity_interventions": [
                    {{
                        "intervention": "умеренное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ],
                "low_intensity_interventions": [
                    {{
                        "intervention": "низкоинтенсивное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ]
            }},
            "monitoring_plan": {{
                "post_discharge_contacts": {{
                    "24_hours": "контакт в течение 24 часов",
                    "72_hours": "контакт в течение 72 часов",
                    "1_week": "контакт через неделю",
                    "1_month": "контакт через месяц"
                }},
                "red_flag_symptoms": ["тревожный симптом 1", "тревожный симптом 2"],
                "emergency_contact_criteria": ["критерий экстренного контакта 1", "критерий экстренного контакта 2"]
            }}
        }}
        """
        
        system_prompt = """Вы специалист по управлению переходами в медицинской помощи с экспертизой в предотвращении повторных госпитализаций.
        Анализируете медицинские, социальные и системные факторы риска повторной госпитализации.
        Используете валидированные инструменты оценки риска и доказательные вмешательства.
        Предоставляете комплексные рекомендации по планированию выписки и координации помощи.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4000
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

    async def transcribe_audio(self, audio_data: bytes, language: str = "ru", medical_context: bool = True) -> Dict[str, Any]:
        """Транскрипция аудио в текст с медицинской терминологией"""
        try:
            # Создаем временный файл для аудио
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Используем Whisper API для транскрипции
                with open(temp_file_path, 'rb') as audio_file:
                    transcript = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                        prompt="Медицинская консультация. Включает медицинскую терминологию, симптомы, диагнозы, лечение." if medical_context else None,
                        response_format="verbose_json",
                        temperature=0.1
                    )
                
                return {
                    "text": transcript.text,
                    "language": transcript.language,
                    "duration": transcript.duration,
                    "segments": [
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "confidence": getattr(segment, 'avg_logprob', 0.0)
                        }
                        for segment in transcript.segments
                    ] if hasattr(transcript, 'segments') else [],
                    "confidence": getattr(transcript, 'avg_logprob', 0.0),
                    "medical_context": medical_context
                }
            finally:
                # Удаляем временный файл
                os.unlink(temp_file_path)
                
        except Exception as e:
            return {
                "error": f"Ошибка транскрипции: {str(e)}",
                "text": "",
                "confidence": 0.0
            }
    
    async def structure_medical_text(self, text: str, document_type: str) -> Dict[str, Any]:
        """Структурирование медицинского текста в формализованные поля"""
        document_templates = {
            "consultation": {
                "fields": ["жалобы", "анамнез", "объективный_осмотр", "диагноз", "лечение", "рекомендации"],
                "description": "консультация врача"
            },
            "prescription": {
                "fields": ["препараты", "дозировка", "способ_применения", "длительность", "противопоказания"],
                "description": "рецепт"
            },
            "discharge": {
                "fields": ["диагноз_при_выписке", "проведенное_лечение", "состояние_при_выписке", "рекомендации", "контрольные_осмотры"],
                "description": "выписной эпикриз"
            },
            "examination": {
                "fields": ["вид_исследования", "показания", "результаты", "заключение", "рекомендации"],
                "description": "результат обследования"
            }
        }
        
        template = document_templates.get(document_type, document_templates["consultation"])
        fields_list = ", ".join(template["fields"])
        
        prompt = f"""
        Структурируйте медицинский текст ({template["description"]}) в формализованные поля.
        
        ИСХОДНЫЙ ТЕКСТ:
        {text}
        
        ТРЕБУЕМЫЕ ПОЛЯ: {fields_list}
        
        Предоставьте структурированный результат в формате JSON:
        {{
            "document_type": "{document_type}",
            "structured_data": {{
                "поле1": "извлеченная информация",
                "поле2": "извлеченная информация"
            }},
            "extracted_entities": {{
                "medications": ["препарат1", "препарат2"],
                "diagnoses": ["диагноз1", "диагноз2"],
                "symptoms": ["симптом1", "симптом2"],
                "procedures": ["процедура1", "процедура2"],
                "dosages": ["дозировка1", "дозировка2"],
                "dates": ["дата1", "дата2"]
            }},
            "completeness_score": "оценка полноты от 1 до 10",
            "missing_fields": ["отсутствующее поле1", "отсутствующее поле2"],
            "confidence_scores": {{
                "поле1": 0.95,
                "поле2": 0.87
            }},
            "suggestions": [
                "предложение по улучшению записи 1",
                "предложение по улучшению записи 2"
            ],
            "quality_indicators": {{
                "terminology_accuracy": "высокая/средняя/низкая",
                "clinical_coherence": "высокая/средняя/низкая",
                "documentation_standards": "соответствует/частично/не_соответствует"
            }}
        }}
        """
        
        system_prompt = """Вы медицинский документовед с экспертизой в структурировании медицинских записей.
        Извлекаете и организуете информацию из неструктурированного медицинского текста.
        Используете стандартную медицинскую терминологию и форматы документации.
        Обеспечиваете высокое качество структурирования и полноту извлечения данных.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2500
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
    
    async def extract_medical_entities(self, text: str) -> Dict[str, Any]:
        """Извлечение медицинских сущностей из текста"""
        prompt = f"""
        Извлеките медицинские сущности из следующего текста:
        
        ТЕКСТ:
        {text}
        
        Предоставьте результат в формате JSON:
        {{
            "medications": [
                {{
                    "name": "название препарата",
                    "dosage": "дозировка",
                    "frequency": "частота приема",
                    "route": "способ введения",
                    "duration": "длительность",
                    "confidence": 0.95
                }}
            ],
            "diagnoses": [
                {{
                    "name": "название диагноза",
                    "icd_code": "код МКБ-10 (если определим)",
                    "type": "основной/сопутствующий/осложнение",
                    "confidence": 0.90
                }}
            ],
            "symptoms": [
                {{
                    "name": "симптом",
                    "severity": "легкий/умеренный/тяжелый",
                    "duration": "длительность",
                    "frequency": "частота",
                    "confidence": 0.85
                }}
            ],
            "procedures": [
                {{
                    "name": "название процедуры",
                    "type": "диагностическая/лечебная/профилактическая",
                    "date": "дата (если указана)",
                    "result": "результат (если указан)",
                    "confidence": 0.88
                }}
            ],
            "laboratory_tests": [
                {{
                    "name": "название анализа",
                    "value": "значение",
                    "unit": "единица измерения",
                    "reference_range": "референсные значения",
                    "interpretation": "норма/повышено/понижено",
                    "confidence": 0.92
                }}
            ],
            "vital_signs": [
                {{
                    "parameter": "параметр",
                    "value": "значение",
                    "unit": "единица",
                    "timestamp": "время измерения",
                    "confidence": 0.95
                }}
            ],
            "anatomical_locations": [
                {{
                    "location": "анатомическая область",
                    "side": "левый/правый/двусторонний",
                    "specificity": "точная локализация",
                    "confidence": 0.87
                }}
            ],
            "temporal_expressions": [
                {{
                    "expression": "временное выражение",
                    "normalized_date": "нормализованная дата",
                    "type": "абсолютная/относительная",
                    "confidence": 0.80
                }}
            ],
            "allergies": [
                {{
                    "allergen": "аллерген",
                    "reaction": "тип реакции",
                    "severity": "тяжесть",
                    "confidence": 0.93
                }}
            ],
            "family_history": [
                {{
                    "condition": "заболевание",
                    "relation": "степень родства",
                    "age_of_onset": "возраст начала",
                    "confidence": 0.85
                }}
            ],
            "social_history": [
                {{
                    "factor": "социальный фактор",
                    "details": "детали",
                    "impact": "влияние на здоровье",
                    "confidence": 0.78
                }}
            ],
            "entity_relationships": [
                {{
                    "entity1": "сущность 1",
                    "relationship": "тип связи",
                    "entity2": "сущность 2",
                    "confidence": 0.82
                }}
            ],
            "extraction_summary": {{
                "total_entities": "общее количество сущностей",
                "high_confidence_entities": "количество с высокой достоверностью",
                "medical_complexity": "низкая/средняя/высокая",
                "text_quality": "хорошее/удовлетворительное/плохое"
            }}
        }}
        """
        
        system_prompt = """Вы специалист по обработке естественного языка в медицине с экспертизой в извлечении медицинских сущностей.
        Точно идентифицируете и классифицируете медицинские термины, препараты, диагнозы и процедуры.
        Используете медицинские стандарты и классификации (МКБ-10, АТХ и др.).
        Оцениваете достоверность извлечения и предоставляете структурированные результаты.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3000
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
    
    async def generate_medical_summary(self, consultation_text: str, patient_history: Optional[str] = None) -> Dict[str, Any]:
        """Генерация медицинского резюме из текста консультации"""
        history_context = f"\n\nИСТОРИЯ ПАЦИЕНТА:\n{patient_history}" if patient_history else ""
        
        prompt = f"""
        Создайте медицинское резюме на основе текста консультации:
        
        ТЕКСТ КОНСУЛЬТАЦИИ:
        {consultation_text}{history_context}
        
        Предоставьте резюме в формате JSON:
        {{
            "executive_summary": {{
                "chief_complaint": "основная жалоба пациента",
                "primary_diagnosis": "основной диагноз",
                "key_findings": ["ключевая находка 1", "ключевая находка 2"],
                "treatment_plan": "краткий план лечения",
                "prognosis": "прогноз"
            }},
            "clinical_assessment": {{
                "presenting_symptoms": [
                    {{
                        "symptom": "симптом",
                        "severity": "тяжесть",
                        "duration": "длительность",
                        "impact": "влияние на качество жизни"
                    }}
                ],
                "physical_examination": {{
                    "general_appearance": "общий вид",
                    "vital_signs": "витальные показатели",
                    "system_specific_findings": {{
                        "cardiovascular": "находки",
                        "respiratory": "находки",
                        "neurological": "находки",
                        "other": "другие находки"
                    }}
                }},
                "diagnostic_impression": {{
                    "primary_diagnosis": "основной диагноз",
                    "differential_diagnoses": ["дифференциальный диагноз 1", "дифференциальный диагноз 2"],
                    "diagnostic_confidence": "высокая/средняя/низкая",
                    "additional_testing_needed": ["необходимое исследование 1", "необходимое исследование 2"]
                }}
            }},
            "management_plan": {{
                "immediate_interventions": [
                    {{
                        "intervention": "вмешательство",
                        "rationale": "обоснование",
                        "timeline": "временные рамки"
                    }}
                ],
                "medications": [
                    {{
                        "medication": "препарат",
                        "indication": "показание",
                        "dosing": "дозировка",
                        "monitoring": "мониторинг"
                    }}
                ],
                "non_pharmacological": [
                    {{
                        "intervention": "немедикаментозное вмешательство",
                        "instructions": "инструкции",
                        "expected_outcome": "ожидаемый результат"
                    }}
                ],
                "follow_up": {{
                    "next_appointment": "следующий визит",
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "red_flags": ["тревожный признак 1", "тревожный признак 2"]
                }}
            }},
            "patient_education": {{
                "key_points": ["ключевой момент 1", "ключевой момент 2"],
                "lifestyle_modifications": ["модификация образа жизни 1", "модификация образа жизни 2"],
                "warning_signs": ["предупреждающий признак 1", "предупреждающий признак 2"],
                "resources": ["ресурс 1", "ресурс 2"]
            }},
            "quality_metrics": {{
                "documentation_completeness": "полнота документации (1-10)",
                "clinical_reasoning_clarity": "ясность клинического мышления (1-10)",
                "treatment_appropriateness": "соответствие лечения (1-10)",
                "patient_safety_considerations": "соображения безопасности (1-10)"
            }},
            "recommendations": {{
                "for_patient": ["рекомендация для пациента 1", "рекомендация для пациента 2"],
                "for_healthcare_team": ["рекомендация для команды 1", "рекомендация для команды 2"],
                "for_documentation": ["рекомендация по документации 1", "рекомендация по документации 2"]
            }}
        }}
        """
        
        system_prompt = """Вы опытный врач-клиницист с экспертизой в создании медицинских резюме и клинической документации.
        Анализируете консультации и создаете структурированные, клинически значимые резюме.
        Обеспечиваете полноту, точность и клиническую релевантность информации.
        Следуете стандартам медицинской документации и клинического мышления.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3500
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
    
    async def validate_medical_record(self, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация и проверка медицинской записи на полноту и корректность"""
        record_json = json.dumps(record_data, ensure_ascii=False, indent=2)
        
        prompt = f"""
        Проведите валидацию медицинской записи на полноту, корректность и соответствие стандартам:
        
        МЕДИЦИНСКАЯ ЗАПИСЬ:
        {record_json}
        
        Предоставьте результат валидации в формате JSON:
        {{
            "validation_summary": {{
                "overall_score": "общая оценка от 1 до 10",
                "completeness_score": "полнота от 1 до 10",
                "accuracy_score": "точность от 1 до 10",
                "compliance_score": "соответствие стандартам от 1 до 10",
                "validation_status": "passed/warning/failed"
            }},
            "required_fields_check": {{
                "present_fields": ["присутствующее поле 1", "присутствующее поле 2"],
                "missing_fields": ["отсутствующее поле 1", "отсутствующее поле 2"],
                "incomplete_fields": ["неполное поле 1", "неполное поле 2"],
                "completeness_percentage": "процент заполненности"
            }},
            "clinical_consistency": {{
                "diagnosis_symptom_alignment": {{
                    "status": "consistent/inconsistent/unclear",
                    "issues": ["проблема согласованности 1", "проблема согласованности 2"]
                }},
                "treatment_diagnosis_alignment": {{
                    "status": "appropriate/questionable/inappropriate",
                    "concerns": ["проблема лечения 1", "проблема лечения 2"]
                }},
                "medication_interactions": {{
                    "status": "safe/caution/dangerous",
                    "interactions": ["взаимодействие 1", "взаимодействие 2"]
                }}
            }},
            "terminology_validation": {{
                "medical_terms_accuracy": "высокая/средняя/низкая",
                "icd_code_validity": "корректные/некорректные/отсутствуют",
                "medication_names": "стандартные/нестандартные/ошибочные",
                "terminology_issues": ["проблема терминологии 1", "проблема терминологии 2"]
            }},
            "data_quality_issues": [
                {{
                    "field": "поле с проблемой",
                    "issue_type": "тип проблемы",
                    "severity": "критическая/высокая/средняя/низкая",
                    "description": "описание проблемы",
                    "suggestion": "предложение по исправлению"
                }}
            ],
            "compliance_check": {{
                "documentation_standards": {{
                    "status": "compliant/partial/non_compliant",
                    "standard": "используемый стандарт",
                    "violations": ["нарушение 1", "нарушение 2"]
                }},
                "privacy_security": {{
                    "phi_protection": "защищена/частично/не_защищена",
                    "access_controls": "соответствует/не_соответствует",
                    "audit_trail": "присутствует/отсутствует"
                }}
            }},
            "improvement_recommendations": [
                {{
                    "category": "категория улучшения",
                    "priority": "высокий/средний/низкий",
                    "recommendation": "рекомендация",
                    "expected_impact": "ожидаемое влияние",
                    "implementation_effort": "усилия по внедрению"
                }}
            ],
            "risk_assessment": {{
                "patient_safety_risks": ["риск безопасности 1", "риск безопасности 2"],
                "legal_compliance_risks": ["правовой риск 1", "правовой риск 2"],
                "quality_of_care_risks": ["риск качества 1", "риск качества 2"],
                "overall_risk_level": "низкий/умеренный/высокий/критический"
            }},
            "automated_corrections": {{
                "spelling_corrections": ["исправление 1", "исправление 2"],
                "format_standardizations": ["стандартизация 1", "стандартизация 2"],
                "code_suggestions": ["предложение кода 1", "предложение кода 2"]
            }}
        }}
        """
        
        system_prompt = """Вы специалист по качеству медицинской документации с экспертизой в валидации медицинских записей.
        Проверяете медицинские записи на полноту, точность, клиническую согласованность и соответствие стандартам.
        Используете медицинские стандарты, классификации и требования к документации.
        Выявляете проблемы качества данных и предоставляете конструктивные рекомендации по улучшению.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3500
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

    async def optimize_doctor_schedule(self, schedule_data: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Оптимизация расписания врача с учетом ограничений и предпочтений"""
        doctor_info = schedule_data.get("doctor", {})
        current_schedule = schedule_data.get("current_schedule", [])
        appointments = schedule_data.get("appointments", [])
        
        doctor_name = doctor_info.get("name", "не указан")
        specialty = doctor_info.get("specialty", "не указана")
        experience = doctor_info.get("experience_years", "не указан")
        preferences = doctor_info.get("preferences", {})
        
        working_hours = constraints.get("working_hours", {})
        break_requirements = constraints.get("break_requirements", {})
        max_patients_per_day = constraints.get("max_patients_per_day", "не указано")
        appointment_types = constraints.get("appointment_types", [])
        
        current_schedule_text = "\n".join([
            f"- {slot.get('time', 'не указано')}: {slot.get('type', 'свободно')} ({slot.get('duration', 0)} мин)"
            for slot in current_schedule
        ])
        
        appointments_text = "\n".join([
            f"- {apt.get('time', 'не указано')}: {apt.get('patient_type', 'обычный')} пациент, {apt.get('complaint', 'не указано')} ({apt.get('estimated_duration', 30)} мин)"
            for apt in appointments
        ])
        
        prompt = f"""
        Оптимизируйте расписание врача с учетом всех ограничений и предпочтений:
        
        ИНФОРМАЦИЯ О ВРАЧЕ:
        - Имя: {doctor_name}
        - Специальность: {specialty}
        - Опыт работы: {experience} лет
        - Предпочтения: {preferences}
        
        ТЕКУЩЕЕ РАСПИСАНИЕ:
        {current_schedule_text}
        
        ЗАПЛАНИРОВАННЫЕ ПРИЕМЫ:
        {appointments_text}
        
        ОГРАНИЧЕНИЯ:
        - Рабочие часы: {working_hours}
        - Требования к перерывам: {break_requirements}
        - Максимум пациентов в день: {max_patients_per_day}
        - Типы приемов: {appointment_types}
        
        Предоставьте оптимизированное расписание в формате JSON:
        {{
            "optimization_summary": {{
                "optimization_score": "оценка оптимизации от 1 до 10",
                "improvements_made": ["улучшение 1", "улучшение 2"],
                "efficiency_gain": "процент повышения эффективности",
                "patient_satisfaction_impact": "влияние на удовлетворенность пациентов",
                "doctor_workload_balance": "баланс рабочей нагрузки"
            }},
            "optimized_schedule": [
                {{
                    "time_slot": "09:00-09:30",
                    "activity": "прием пациента/перерыв/административная работа",
                    "patient_type": "первичный/повторный/срочный",
                    "estimated_duration": 30,
                    "complexity_level": "низкая/средняя/высокая",
                    "preparation_time": 5,
                    "buffer_time": 5,
                    "priority": "высокий/средний/низкий",
                    "notes": "особые замечания"
                }}
            ],
            "schedule_analytics": {{
                "total_working_hours": "общее время работы",
                "patient_slots": "количество слотов для пациентов",
                "break_time": "время перерывов",
                "administrative_time": "время на административные задачи",
                "utilization_rate": "коэффициент использования времени",
                "peak_hours": ["час пик 1", "час пик 2"],
                "low_activity_periods": ["период низкой активности 1"]
            }},
            "constraint_compliance": {{
                "working_hours_respected": true/false,
                "break_requirements_met": true/false,
                "patient_limit_observed": true/false,
                "appointment_types_balanced": true/false,
                "doctor_preferences_considered": true/false,
                "compliance_score": "оценка соблюдения ограничений"
            }},
            "recommendations": {{
                "immediate_actions": [
                    {{
                        "action": "немедленное действие",
                        "rationale": "обоснование",
                        "expected_impact": "ожидаемый эффект",
                        "implementation_difficulty": "легко/средне/сложно"
                    }}
                ],
                "schedule_adjustments": [
                    {{
                        "adjustment": "корректировка расписания",
                        "reason": "причина корректировки",
                        "benefit": "преимущество",
                        "trade_off": "компромисс"
                    }}
                ],
                "long_term_improvements": [
                    {{
                        "improvement": "долгосрочное улучшение",
                        "description": "описание",
                        "timeline": "временные рамки",
                        "resources_needed": "необходимые ресурсы"
                    }}
                ]
            }},
            "risk_assessment": {{
                "scheduling_conflicts": ["потенциальный конфликт 1", "потенциальный конфликт 2"],
                "overload_risks": ["риск перегрузки 1", "риск перегрузки 2"],
                "patient_wait_times": "прогноз времени ожидания",
                "doctor_fatigue_factors": ["фактор усталости 1", "фактор усталости 2"],
                "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
            }},
            "alternative_schedules": [
                {{
                    "scenario": "альтернативный сценарий",
                    "description": "описание сценария",
                    "pros": ["преимущество 1", "преимущество 2"],
                    "cons": ["недостаток 1", "недостаток 2"],
                    "suitability_score": "оценка подходящности"
                }}
            ]
        }}
        """
        
        system_prompt = """Вы специалист по оптимизации медицинских расписаний с экспертизой в управлении временем и ресурсами.
        Создаете эффективные расписания, учитывающие потребности врачей, пациентов и медицинского учреждения.
        Используете принципы lean-менеджмента и данные о производительности для оптимизации.
        Обеспечиваете баланс между эффективностью работы и качеством медицинской помощи.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4000
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
    
    async def predict_appointment_duration(self, appointment_data: Dict[str, Any], historical_data: List[Dict]) -> Dict[str, Any]:
        """Прогнозирование длительности приема на основе исторических данных"""
        patient_info = appointment_data.get("patient", {})
        appointment_type = appointment_data.get("type", "не указан")
        complaint = appointment_data.get("complaint", "не указана")
        doctor_specialty = appointment_data.get("doctor_specialty", "не указана")
        is_first_visit = appointment_data.get("is_first_visit", False)
        
        # Обработка исторических данных
        historical_summary = {
            "total_appointments": len(historical_data),
            "average_duration": sum(apt.get("actual_duration", 30) for apt in historical_data) / len(historical_data) if historical_data else 30,
            "duration_range": {
                "min": min(apt.get("actual_duration", 30) for apt in historical_data) if historical_data else 15,
                "max": max(apt.get("actual_duration", 30) for apt in historical_data) if historical_data else 60
            }
        }
        
        similar_cases = [
            apt for apt in historical_data 
            if apt.get("type") == appointment_type or apt.get("complaint", "").lower() in complaint.lower()
        ]
        
        prompt = f"""
        Спрогнозируйте длительность медицинского приема на основе данных:
        
        ИНФОРМАЦИЯ О ПРИЕМЕ:
        - Тип приема: {appointment_type}
        - Жалоба пациента: {complaint}
        - Специальность врача: {doctor_specialty}
        - Первичный визит: {"да" if is_first_visit else "нет"}
        - Информация о пациенте: {patient_info}
        
        ИСТОРИЧЕСКИЕ ДАННЫЕ:
        - Всего приемов в базе: {historical_summary["total_appointments"]}
        - Средняя длительность: {historical_summary["average_duration"]:.1f} минут
        - Диапазон длительности: {historical_summary["duration_range"]["min"]}-{historical_summary["duration_range"]["max"]} минут
        - Похожих случаев: {len(similar_cases)}
        
        Предоставьте прогноз в формате JSON:
        {{
            "duration_prediction": {{
                "predicted_duration": "прогнозируемая длительность в минутах",
                "confidence_level": "высокая/средняя/низкая",
                "prediction_range": {{
                    "min_duration": "минимальная длительность",
                    "max_duration": "максимальная длительность",
                    "most_likely": "наиболее вероятная длительность"
                }},
                "factors_considered": ["фактор 1", "фактор 2", "фактор 3"]
            }},
            "duration_breakdown": {{
                "consultation_time": "время консультации",
                "examination_time": "время осмотра",
                "documentation_time": "время документирования",
                "patient_education_time": "время обучения пациента",
                "buffer_time": "буферное время"
            }},
            "complexity_assessment": {{
                "case_complexity": "простой/средний/сложный/очень сложный",
                "complexity_factors": [
                    {{
                        "factor": "фактор сложности",
                        "impact": "влияние на длительность",
                        "weight": "вес фактора"
                    }}
                ],
                "additional_time_needed": "дополнительное время при осложнениях"
            }},
            "historical_analysis": {{
                "similar_cases_found": {len(similar_cases)},
                "average_duration_similar": "средняя длительность похожих случаев",
                "duration_variance": "вариативность длительности",
                "seasonal_patterns": "сезонные паттерны",
                "day_of_week_impact": "влияние дня недели"
            }},
            "risk_factors": {{
                "overtime_probability": "вероятность превышения времени",
                "potential_delays": ["потенциальная задержка 1", "потенциальная задержка 2"],
                "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
            }},
            "scheduling_recommendations": {{
                "optimal_time_slot": "оптимальное время для приема",
                "buffer_before": "буферное время до приема",
                "buffer_after": "буферное время после приема",
                "special_preparations": ["специальная подготовка 1", "специальная подготовка 2"],
                "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
            }},
            "quality_indicators": {{
                "patient_satisfaction_factors": ["фактор удовлетворенности 1", "фактор удовлетворенности 2"],
                "clinical_outcome_predictors": ["предиктор исхода 1", "предиктор исхода 2"],
                "efficiency_metrics": ["метрика эффективности 1", "метрика эффективности 2"]
            }}
        }}
        """
        
        system_prompt = """Вы специалист по анализу медицинских данных с экспертизой в прогнозировании временных затрат на медицинские процедуры.
        Анализируете исторические данные и клинические факторы для точного прогнозирования длительности приемов.
        Учитываете сложность случаев, особенности пациентов и специфику медицинских специальностей.
        Предоставляете практические рекомендации по планированию времени и оптимизации расписания.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3000
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
    
    async def suggest_optimal_slots(self, doctor_profile: Dict[str, Any], patient_requirements: Dict[str, Any], available_slots: List[Dict]) -> Dict[str, Any]:
        """Предложение оптимальных временных слотов для записи"""
        doctor_name = doctor_profile.get("name", "не указан")
        specialty = doctor_profile.get("specialty", "не указана")
        working_patterns = doctor_profile.get("working_patterns", {})
        performance_metrics = doctor_profile.get("performance_metrics", {})
        
        patient_preferences = patient_requirements.get("preferences", {})
        urgency_level = patient_requirements.get("urgency", "обычная")
        appointment_type = patient_requirements.get("type", "консультация")
        estimated_duration = patient_requirements.get("estimated_duration", 30)
        
        slots_text = "\n".join([
            f"- {slot.get('date', 'не указано')} {slot.get('time', 'не указано')}: {slot.get('duration', 30)} мин (загрузка: {slot.get('current_load', 0)}%)"
            for slot in available_slots
        ])
        
        prompt = f"""
        Предложите оптимальные временные слоты для записи пациента:
        
        ПРОФИЛЬ ВРАЧА:
        - Имя: {doctor_name}
        - Специальность: {specialty}
        - Паттерны работы: {working_patterns}
        - Показатели производительности: {performance_metrics}
        
        ТРЕБОВАНИЯ ПАЦИЕНТА:
        - Предпочтения: {patient_preferences}
        - Срочность: {urgency_level}
        - Тип приема: {appointment_type}
        - Ожидаемая длительность: {estimated_duration} минут
        
        ДОСТУПНЫЕ СЛОТЫ:
        {slots_text}
        
        Предоставьте рекомендации в формате JSON:
        {{
            "optimal_slots": [
                {{
                    "slot_id": "идентификатор слота",
                    "date": "дата",
                    "time": "время",
                    "optimality_score": "оценка оптимальности от 1 до 10",
                    "ranking": "позиция в рейтинге",
                    "advantages": ["преимущество 1", "преимущество 2"],
                    "considerations": ["соображение 1", "соображение 2"],
                    "doctor_performance_at_time": "производительность врача в это время",
                    "patient_convenience": "удобство для пациента",
                    "clinic_efficiency": "эффективность для клиники"
                }}
            ],
            "selection_criteria": {{
                "primary_factors": [
                    {{
                        "factor": "основной фактор",
                        "weight": "вес фактора",
                        "description": "описание влияния"
                    }}
                ],
                "secondary_factors": [
                    {{
                        "factor": "второстепенный фактор",
                        "weight": "вес фактора",
                        "description": "описание влияния"
                    }}
                ],
                "urgency_adjustments": "корректировки по срочности"
            }},
            "time_analysis": {{
                "peak_performance_hours": ["час пик производительности 1", "час пик производительности 2"],
                "patient_preference_alignment": "соответствие предпочтениям пациента",
                "waiting_time_predictions": {{
                    "before_appointment": "время ожидания до приема",
                    "in_clinic": "время ожидания в клинике",
                    "total_visit_duration": "общая длительность визита"
                }},
                "traffic_patterns": "паттерны загруженности клиники"
            }},
            "alternative_options": [
                {{
                    "option": "альтернативный вариант",
                    "description": "описание варианта",
                    "trade_offs": ["компромисс 1", "компромисс 2"],
                    "suitability": "подходящность для пациента"
                }}
            ],
            "scheduling_recommendations": {{
                "preparation_instructions": ["инструкция по подготовке 1", "инструкция по подготовке 2"],
                "arrival_time": "рекомендуемое время прибытия",
                "documents_needed": ["необходимый документ 1", "необходимый документ 2"],
                "special_considerations": ["особое соображение 1", "особое соображение 2"]
            }},
            "optimization_insights": {{
                "schedule_efficiency": "эффективность расписания",
                "resource_utilization": "использование ресурсов",
                "patient_flow_impact": "влияние на поток пациентов",
                "revenue_optimization": "оптимизация доходов",
                "quality_of_care_factors": ["фактор качества помощи 1", "фактор качества помощи 2"]
            }}
        }}
        """
        
        system_prompt = """Вы специалист по оптимизации медицинского планирования с экспертизой в анализе временных слотов и предпочтений.
        Анализируете множественные факторы для предложения оптимальных временных слотов для медицинских приемов.
        Учитываете производительность врачей, удобство пациентов и эффективность клиники.
        Предоставляете обоснованные рекомендации с учетом всех заинтересованных сторон.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3500
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
    
    async def analyze_workload_distribution(self, doctors_data: List[Dict], time_period: str) -> Dict[str, Any]:
        """Анализ распределения рабочей нагрузки между врачами"""
        doctors_summary = []
        for doctor in doctors_data:
            summary = {
                "name": doctor.get("name", "не указан"),
                "specialty": doctor.get("specialty", "не указана"),
                "total_appointments": len(doctor.get("appointments", [])),
                "total_hours": doctor.get("total_working_hours", 0),
                "patient_load": doctor.get("patient_load", 0)
            }
            doctors_summary.append(summary)
        
        doctors_text = "\n".join([
            f"- {doc['name']} ({doc['specialty']}): {doc['total_appointments']} приемов, {doc['total_hours']} часов, нагрузка {doc['patient_load']}%"
            for doc in doctors_summary
        ])
        
        prompt = f"""
        Проанализируйте распределение рабочей нагрузки между врачами:
        
        ПЕРИОД АНАЛИЗА: {time_period}
        
        ДАННЫЕ ПО ВРАЧАМ:
        {doctors_text}
        
        Предоставьте анализ в формате JSON:
        {{
            "workload_analysis": {{
                "analysis_period": "{time_period}",
                "total_doctors": {len(doctors_data)},
                "overall_utilization": "общий коэффициент использования",
                "load_balance_score": "оценка сбалансированности нагрузки от 1 до 10",
                "efficiency_rating": "рейтинг эффективности"
            }},
            "doctor_performance": [
                {{
                    "doctor_name": "имя врача",
                    "specialty": "специальность",
                    "workload_metrics": {{
                        "utilization_rate": "коэффициент использования",
                        "patient_throughput": "пропускная способность",
                        "average_appointment_duration": "средняя длительность приема",
                        "overtime_frequency": "частота переработок",
                        "cancellation_rate": "частота отмен"
                    }},
                    "performance_category": "высокая/средняя/низкая производительность",
                    "workload_status": "недогружен/оптимально/перегружен/критически перегружен"
                }}
            ],
            "specialty_analysis": [
                {{
                    "specialty": "специальность",
                    "total_doctors": "количество врачей",
                    "average_workload": "средняя нагрузка",
                    "demand_vs_capacity": "соотношение спроса и мощности",
                    "bottlenecks": ["узкое место 1", "узкое место 2"],
                    "optimization_opportunities": ["возможность оптимизации 1", "возможность оптимизации 2"]
                }}
            ],
            "load_distribution": {{
                "underutilized_doctors": [
                    {{
                        "doctor": "имя врача",
                        "current_load": "текущая нагрузка",
                        "capacity_available": "доступная мощность",
                        "potential_additional_patients": "потенциальные дополнительные пациенты"
                    }}
                ],
                "overloaded_doctors": [
                    {{
                        "doctor": "имя врача",
                        "current_load": "текущая нагрузка",
                        "excess_load": "избыточная нагрузка",
                        "redistribution_needed": "необходимое перераспределение"
                    }}
                ],
                "optimal_load_doctors": [
                    {{
                        "doctor": "имя врача",
                        "load_efficiency": "эффективность нагрузки",
                        "best_practices": ["лучшая практика 1", "лучшая практика 2"]
                    }}
                ]
            }},
            "redistribution_recommendations": [
                {{
                    "recommendation": "рекомендация по перераспределению",
                    "from_doctor": "от врача",
                    "to_doctor": "к врачу",
                    "patient_volume": "объем пациентов",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_complexity": "сложность внедрения"
                }}
            ],
            "capacity_optimization": {{
                "additional_capacity_needed": "необходимая дополнительная мощность",
                "specialties_requiring_staff": ["специальность 1", "специальность 2"],
                "schedule_adjustments": ["корректировка расписания 1", "корректировка расписания 2"],
                "resource_reallocation": ["перераспределение ресурса 1", "перераспределение ресурса 2"]
            }},
            "quality_impact": {{
                "patient_satisfaction_risks": ["риск удовлетворенности 1", "риск удовлетворенности 2"],
                "care_quality_indicators": ["индикатор качества 1", "индикатор качества 2"],
                "burnout_risk_assessment": "оценка риска выгорания",
                "recommended_interventions": ["рекомендуемое вмешательство 1", "рекомендуемое вмешательство 2"]
            }},
            "financial_analysis": {{
                "revenue_optimization_potential": "потенциал оптимизации доходов",
                "cost_efficiency_improvements": ["улучшение эффективности затрат 1", "улучшение эффективности затрат 2"],
                "roi_of_redistribution": "ROI от перераспределения нагрузки"
            }}
        }}
        """
        
        system_prompt = """Вы специалист по анализу рабочей нагрузки в медицинских учреждениях с экспертизой в оптимизации ресурсов.
        Анализируете распределение нагрузки между врачами и предлагаете стратегии оптимизации.
        Учитываете производительность, качество медицинской помощи и удовлетворенность персонала.
        Предоставляете практические рекомендации по перераспределению нагрузки и улучшению эффективности.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4000
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
    
    async def generate_shift_recommendations(self, department_data: Dict[str, Any], staffing_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация рекомендаций по составлению смен и графиков работы"""
        department_name = department_data.get("name", "не указано")
        staff_list = department_data.get("staff", [])
        current_shifts = department_data.get("current_shifts", [])
        patient_flow_patterns = department_data.get("patient_flow_patterns", {})
        
        min_staff_per_shift = staffing_requirements.get("min_staff_per_shift", 1)
        coverage_hours = staffing_requirements.get("coverage_hours", "24/7")
        skill_requirements = staffing_requirements.get("skill_requirements", [])
        compliance_rules = staffing_requirements.get("compliance_rules", {})
        
        staff_text = "\n".join([
            f"- {staff.get('name', 'не указан')} ({staff.get('role', 'не указана')}, опыт: {staff.get('experience', 0)} лет, предпочтения: {staff.get('preferences', {})})"
            for staff in staff_list
        ])
        
        shifts_text = "\n".join([
            f"- {shift.get('time', 'не указано')}: {len(shift.get('staff', []))} сотрудников, загрузка {shift.get('workload', 0)}%"
            for shift in current_shifts
        ])
        
        prompt = f"""
        Создайте оптимальные рекомендации по составлению смен и графиков работы:
        
        ИНФОРМАЦИЯ О ОТДЕЛЕНИИ:
        - Название: {department_name}
        - Паттерны потока пациентов: {patient_flow_patterns}
        
        ПЕРСОНАЛ:
        {staff_text}
        
        ТЕКУЩИЕ СМЕНЫ:
        {shifts_text}
        
        ТРЕБОВАНИЯ К ПЕРСОНАЛУ:
        - Минимум сотрудников на смену: {min_staff_per_shift}
        - Часы покрытия: {coverage_hours}
        - Требования к навыкам: {skill_requirements}
        - Правила соответствия: {compliance_rules}
        
        Предоставьте рекомендации в формате JSON:
        {{
            "shift_recommendations": {{
                "optimization_approach": "подход к оптимизации",
                "coverage_strategy": "стратегия покрытия",
                "staff_utilization_target": "целевое использование персонала",
                "quality_assurance_measures": ["мера обеспечения качества 1", "мера обеспечения качества 2"]
            }},
            "recommended_shifts": [
                {{
                    "shift_name": "название смены",
                    "time_period": "временной период",
                    "staff_assignments": [
                        {{
                            "staff_member": "сотрудник",
                            "role": "роль",
                            "responsibilities": ["обязанность 1", "обязанность 2"],
                            "workload_percentage": "процент нагрузки"
                        }}
                    ],
                    "shift_characteristics": {{
                        "patient_volume_expected": "ожидаемый объем пациентов",
                        "complexity_level": "уровень сложности",
                        "critical_tasks": ["критическая задача 1", "критическая задача 2"],
                        "support_requirements": ["требование поддержки 1", "требование поддержки 2"]
                    }}
                }}
            ],
            "staffing_optimization": {{
                "cross_training_recommendations": [
                    {{
                        "staff_member": "сотрудник",
                        "additional_skills_needed": ["навык 1", "навык 2"],
                        "training_priority": "высокий/средний/низкий",
                        "expected_benefit": "ожидаемая польза"
                    }}
                ],
                "workload_balancing": [
                    {{
                        "issue": "проблема баланса нагрузки",
                        "solution": "решение",
                        "affected_staff": ["сотрудник 1", "сотрудник 2"],
                        "implementation_steps": ["шаг 1", "шаг 2"]
                    }}
                ],
                "flexibility_measures": ["мера гибкости 1", "мера гибкости 2"]
            }},
            "compliance_analysis": {{
                "labor_law_compliance": {{
                    "status": "соответствует/не соответствует",
                    "violations": ["нарушение 1", "нарушение 2"],
                    "corrective_actions": ["корректирующее действие 1", "корректирующее действие 2"]
                }},
                "medical_standards_compliance": {{
                    "status": "соответствует/не соответствует",
                    "requirements_met": ["выполненное требование 1", "выполненное требование 2"],
                    "gaps": ["пробел 1", "пробел 2"]
                }},
                "union_agreement_compliance": "соответствие соглашениям с профсоюзом"
            }},
            "contingency_planning": {{
                "sick_leave_coverage": [
                    {{
                        "scenario": "сценарий больничного",
                        "coverage_plan": "план покрытия",
                        "backup_staff": ["резервный сотрудник 1", "резервный сотрудник 2"],
                        "service_impact": "влияние на услуги"
                    }}
                ],
                "emergency_protocols": [
                    {{
                        "emergency_type": "тип чрезвычайной ситуации",
                        "staffing_response": "ответ персонала",
                        "escalation_procedures": ["процедура эскалации 1", "процедура эскалации 2"]
                    }}
                ],
                "seasonal_adjustments": ["сезонная корректировка 1", "сезонная корректировка 2"]
            }},
            "performance_metrics": {{
                "key_indicators": [
                    {{
                        "metric": "ключевой показатель",
                        "target_value": "целевое значение",
                        "measurement_method": "метод измерения",
                        "reporting_frequency": "частота отчетности"
                    }}
                ],
                "quality_measures": ["мера качества 1", "мера качества 2"],
                "efficiency_benchmarks": ["бенчмарк эффективности 1", "бенчмарк эффективности 2"]
            }},
            "implementation_plan": {{
                "phase_1": {{
                    "duration": "длительность фазы 1",
                    "activities": ["активность 1", "активность 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_2": {{
                    "duration": "длительность фазы 2",
                    "activities": ["активность 1", "активность 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "monitoring_schedule": "график мониторинга",
                "adjustment_triggers": ["триггер корректировки 1", "триггер корректировки 2"]
            }}
        }}
        """
        
        system_prompt = """Вы специалист по управлению медицинским персоналом с экспертизой в составлении оптимальных графиков работы.
        Создаете эффективные системы смен, учитывающие потребности пациентов, возможности персонала и требования регулирования.
        Используете принципы управления человеческими ресурсами и данные о производительности для оптимизации.
        Обеспечиваете соблюдение трудового законодательства и медицинских стандартов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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

    async def analyze_documentation_quality(self, medical_records: List[Dict], quality_standards: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ качества медицинской документации"""
        records_summary = []
        for record in medical_records[:10]:  # Ограничиваем для анализа
            summary = {
                "record_id": record.get("id", "не указан"),
                "record_type": record.get("type", "не указан"),
                "completeness": len([k for k, v in record.items() if v]) / len(record) * 100 if record else 0,
                "fields_count": len(record),
                "has_diagnosis": bool(record.get("diagnosis")),
                "has_treatment": bool(record.get("treatment")),
                "has_symptoms": bool(record.get("symptoms"))
            }
            records_summary.append(summary)
        
        standards_text = "\n".join([f"- {k}: {v}" for k, v in quality_standards.items()])
        records_text = "\n".join([
            f"Запись {r['record_id']}: {r['record_type']}, полнота {r['completeness']:.1f}%, диагноз: {'есть' if r['has_diagnosis'] else 'нет'}"
            for r in records_summary
        ])
        
        prompt = f"""
        Проанализируйте качество медицинской документации на соответствие стандартам:
        
        СТАНДАРТЫ КАЧЕСТВА:
        {standards_text}
        
        АНАЛИЗИРУЕМЫЕ ЗАПИСИ:
        {records_text}
        
        Предоставьте анализ в формате JSON:
        {{
            "quality_assessment": {{
                "overall_quality_score": "общая оценка качества от 1 до 10",
                "records_analyzed": {len(records_summary)},
                "compliance_rate": "процент соответствия стандартам",
                "quality_trend": "улучшается/стабильно/ухудшается",
                "benchmark_comparison": "сравнение с эталонными показателями"
            }},
            "quality_metrics": {{
                "completeness_score": "оценка полноты документации",
                "accuracy_score": "оценка точности информации",
                "timeliness_score": "оценка своевременности заполнения",
                "consistency_score": "оценка согласованности данных",
                "legibility_score": "оценка читаемости записей"
            }},
            "documentation_analysis": [
                {{
                    "category": "категория документации",
                    "quality_level": "высокое/среднее/низкое",
                    "common_issues": ["проблема 1", "проблема 2"],
                    "compliance_gaps": ["пробел соответствия 1", "пробел соответствия 2"],
                    "improvement_potential": "потенциал улучшения"
                }}
            ],
            "critical_findings": [
                {{
                    "finding": "критическая находка",
                    "severity": "критическая/высокая/средняя/низкая",
                    "impact": "влияние на качество помощи",
                    "frequency": "частота встречаемости",
                    "recommended_action": "рекомендуемое действие"
                }}
            ],
            "best_practices_adherence": {{
                "clinical_guidelines": {{
                    "adherence_rate": "процент соблюдения",
                    "deviations": ["отклонение 1", "отклонение 2"],
                    "justifications": ["обоснование 1", "обоснование 2"]
                }},
                "documentation_standards": {{
                    "format_compliance": "соответствие формату",
                    "required_fields": "заполнение обязательных полей",
                    "signature_requirements": "требования к подписям"
                }},
                "legal_requirements": {{
                    "regulatory_compliance": "соответствие нормативам",
                    "audit_readiness": "готовность к аудиту",
                    "risk_areas": ["область риска 1", "область риска 2"]
                }}
            }},
            "improvement_recommendations": [
                {{
                    "area": "область улучшения",
                    "priority": "высокий/средний/низкий",
                    "recommendation": "конкретная рекомендация",
                    "expected_impact": "ожидаемое влияние",
                    "implementation_effort": "усилия по внедрению",
                    "timeline": "временные рамки",
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"]
                }}
            ],
            "training_needs": [
                {{
                    "skill_area": "область навыков",
                    "target_audience": "целевая аудитория",
                    "training_type": "тип обучения",
                    "urgency": "срочность",
                    "expected_outcome": "ожидаемый результат"
                }}
            ],
            "quality_monitoring": {{
                "key_indicators": ["ключевой индикатор 1", "ключевой индикатор 2"],
                "monitoring_frequency": "частота мониторинга",
                "alert_thresholds": "пороговые значения для предупреждений",
                "reporting_schedule": "график отчетности"
            }}
        }}
        """
        
        system_prompt = """Вы специалист по качеству медицинской документации с экспертизой в аудите и улучшении медицинских записей.
        Анализируете документацию на соответствие медицинским стандартам, нормативным требованиям и лучшим практикам.
        Выявляете проблемы качества и предоставляете практические рекомендации по улучшению.
        Обеспечиваете соблюдение требований безопасности пациентов и правовых норм.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4000
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
    
    async def detect_documentation_gaps(self, patient_record: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Выявление пробелов в медицинской документации"""
        record_fields = list(patient_record.keys())
        missing_fields = [field for field in required_fields if field not in patient_record or not patient_record.get(field)]
        present_fields = [field for field in required_fields if field in patient_record and patient_record.get(field)]
        
        record_summary = {
            "total_fields": len(patient_record),
            "required_fields": len(required_fields),
            "present_fields": len(present_fields),
            "missing_fields": len(missing_fields),
            "completeness_percentage": (len(present_fields) / len(required_fields)) * 100 if required_fields else 100
        }
        
        record_text = json.dumps(patient_record, ensure_ascii=False, indent=2)
        required_text = ", ".join(required_fields)
        missing_text = ", ".join(missing_fields) if missing_fields else "нет"
        
        prompt = f"""
        Выявите пробелы в медицинской документации пациента:
        
        МЕДИЦИНСКАЯ ЗАПИСЬ:
        {record_text}
        
        ОБЯЗАТЕЛЬНЫЕ ПОЛЯ: {required_text}
        ОТСУТСТВУЮЩИЕ ПОЛЯ: {missing_text}
        СТАТИСТИКА: {record_summary}
        
        Предоставьте анализ пробелов в формате JSON:
        {{
            "gap_analysis": {{
                "completeness_score": {record_summary['completeness_percentage']:.1f},
                "total_gaps": {len(missing_fields)},
                "critical_gaps": "количество критических пробелов",
                "minor_gaps": "количество незначительных пробелов",
                "gap_severity": "критическая/высокая/средняя/низкая"
            }},
            "missing_information": [
                {{
                    "field": "отсутствующее поле",
                    "category": "категория информации",
                    "importance": "критическая/высокая/средняя/низкая",
                    "impact_on_care": "влияние на качество помощи",
                    "regulatory_requirement": "нормативное требование",
                    "suggested_source": "предлагаемый источник информации",
                    "collection_method": "метод сбора информации"
                }}
            ],
            "incomplete_sections": [
                {{
                    "section": "неполная секция",
                    "missing_elements": ["отсутствующий элемент 1", "отсутствующий элемент 2"],
                    "completion_percentage": "процент заполненности",
                    "priority_for_completion": "приоритет заполнения",
                    "clinical_significance": "клиническая значимость"
                }}
            ],
            "data_quality_issues": [
                {{
                    "issue": "проблема качества данных",
                    "field": "проблемное поле",
                    "issue_type": "тип проблемы",
                    "severity": "серьезность",
                    "correction_needed": "необходимая коррекция",
                    "validation_rule": "правило валидации"
                }}
            ],
            "compliance_gaps": {{
                "regulatory_compliance": {{
                    "missing_required_fields": ["обязательное поле 1", "обязательное поле 2"],
                    "non_compliant_formats": ["некорректный формат 1", "некорректный формат 2"],
                    "signature_issues": ["проблема подписи 1", "проблема подписи 2"]
                }},
                "clinical_standards": {{
                    "missing_assessments": ["отсутствующая оценка 1", "отсутствующая оценка 2"],
                    "incomplete_histories": ["неполная история 1", "неполная история 2"],
                    "missing_follow_up": ["отсутствующее наблюдение 1", "отсутствующее наблюдение 2"]
                }}
            }},
            "risk_assessment": {{
                "patient_safety_risks": ["риск безопасности 1", "риск безопасности 2"],
                "legal_risks": ["правовой риск 1", "правовой риск 2"],
                "quality_of_care_risks": ["риск качества 1", "риск качества 2"],
                "continuity_of_care_risks": ["риск непрерывности 1", "риск непрерывности 2"]
            }},
            "remediation_plan": [
                {{
                    "gap": "пробел для устранения",
                    "action": "необходимое действие",
                    "responsible_party": "ответственная сторона",
                    "timeline": "временные рамки",
                    "resources_needed": "необходимые ресурсы",
                    "success_criteria": "критерии успеха"
                }}
            ],
            "prevention_strategies": [
                {{
                    "strategy": "стратегия предотвращения",
                    "implementation": "способ внедрения",
                    "target_audience": "целевая аудитория",
                    "expected_outcome": "ожидаемый результат"
                }}
            ]
        }}
        """
        
        system_prompt = """Вы специалист по анализу медицинской документации с экспертизой в выявлении пробелов и недостатков.
        Систематически анализируете медицинские записи на полноту, точность и соответствие требованиям.
        Выявляете критические пробелы, влияющие на безопасность пациентов и качество помощи.
        Предоставляете практические рекомендации по устранению недостатков документации.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3500
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
    
    async def suggest_documentation_improvements(self, record_analysis: Dict[str, Any], best_practices: Dict[str, Any]) -> Dict[str, Any]:
        """Предложение улучшений для медицинской документации"""
        analysis_text = json.dumps(record_analysis, ensure_ascii=False, indent=2)
        practices_text = json.dumps(best_practices, ensure_ascii=False, indent=2)
        
        prompt = f"""
        На основе анализа медицинской документации предложите улучшения:
        
        АНАЛИЗ ДОКУМЕНТАЦИИ:
        {analysis_text}
        
        ЛУЧШИЕ ПРАКТИКИ:
        {practices_text}
        
        Предоставьте рекомендации по улучшению в формате JSON:
        {{
            "improvement_summary": {{
                "total_recommendations": "общее количество рекомендаций",
                "priority_areas": ["приоритетная область 1", "приоритетная область 2"],
                "expected_impact": "ожидаемое влияние улучшений",
                "implementation_complexity": "сложность внедрения",
                "estimated_timeline": "предполагаемые временные рамки"
            }},
            "structural_improvements": [
                {{
                    "area": "область структурного улучшения",
                    "current_issue": "текущая проблема",
                    "proposed_solution": "предлагаемое решение",
                    "benefits": ["преимущество 1", "преимущество 2"],
                    "implementation_steps": ["шаг 1", "шаг 2"],
                    "resources_required": ["ресурс 1", "ресурс 2"],
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"]
                }}
            ],
            "content_improvements": [
                {{
                    "section": "секция для улучшения",
                    "enhancement": "улучшение содержания",
                    "rationale": "обоснование улучшения",
                    "clinical_benefit": "клиническая польза",
                    "patient_safety_impact": "влияние на безопасность пациента",
                    "compliance_benefit": "польза для соответствия требованиям"
                }}
            ],
            "process_improvements": [
                {{
                    "process": "процесс для улучшения",
                    "current_workflow": "текущий рабочий процесс",
                    "improved_workflow": "улучшенный рабочий процесс",
                    "efficiency_gain": "повышение эффективности",
                    "quality_improvement": "улучшение качества",
                    "training_requirements": ["требование к обучению 1", "требование к обучению 2"]
                }}
            ],
            "technology_recommendations": [
                {{
                    "technology": "рекомендуемая технология",
                    "purpose": "цель использования",
                    "features": ["функция 1", "функция 2"],
                    "integration_requirements": ["требование интеграции 1", "требование интеграции 2"],
                    "cost_benefit_analysis": "анализ затрат и выгод",
                    "implementation_timeline": "график внедрения"
                }}
            ],
            "quality_assurance_measures": [
                {{
                    "measure": "мера обеспечения качества",
                    "objective": "цель меры",
                    "implementation_method": "метод внедрения",
                    "monitoring_approach": "подход к мониторингу",
                    "frequency": "частота применения",
                    "responsible_parties": ["ответственная сторона 1", "ответственная сторона 2"]
                }}
            ],
            "training_programs": [
                {{
                    "program": "программа обучения",
                    "target_audience": "целевая аудитория",
                    "learning_objectives": ["цель обучения 1", "цель обучения 2"],
                    "delivery_method": "метод проведения",
                    "duration": "продолжительность",
                    "assessment_criteria": ["критерий оценки 1", "критерий оценки 2"],
                    "certification_requirements": "требования к сертификации"
                }}
            ],
            "compliance_enhancements": {{
                "regulatory_alignment": [
                    {{
                        "regulation": "нормативный акт",
                        "current_compliance_level": "текущий уровень соответствия",
                        "required_changes": ["необходимое изменение 1", "необходимое изменение 2"],
                        "compliance_timeline": "график достижения соответствия"
                    }}
                ],
                "audit_preparedness": [
                    {{
                        "audit_area": "область аудита",
                        "preparation_steps": ["шаг подготовки 1", "шаг подготовки 2"],
                        "documentation_requirements": ["требование к документации 1", "требование к документации 2"],
                        "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                    }}
                ]
            }},
            "performance_monitoring": {{
                "key_performance_indicators": [
                    {{
                        "indicator": "ключевой показатель",
                        "measurement_method": "метод измерения",
                        "target_value": "целевое значение",
                        "reporting_frequency": "частота отчетности",
                        "responsible_party": "ответственная сторона"
                    }}
                ],
                "quality_dashboards": [
                    {{
                        "dashboard": "панель качества",
                        "metrics_displayed": ["отображаемая метрика 1", "отображаемая метрика 2"],
                        "update_frequency": "частота обновления",
                        "target_users": ["целевой пользователь 1", "целевой пользователь 2"]
                    }}
                ]
            }},
            "implementation_roadmap": {{
                "phase_1": {{
                    "duration": "длительность фазы 1",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_2": {{
                    "duration": "длительность фазы 2",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_3": {{
                    "duration": "длительность фазы 3",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }}
            }}
        }}
        """
        
        system_prompt = """Вы консультант по улучшению качества медицинской документации с экспертизой в оптимизации процессов и внедрении лучших практик.
        Разрабатываете комплексные стратегии улучшения документации, учитывающие клинические, технологические и регулятивные аспекты.
        Предоставляете практические, реализуемые рекомендации с четкими планами внедрения и показателями успеха.
        Обеспечиваете соответствие международным стандартам качества и безопасности пациентов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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
    
    async def validate_clinical_consistency(self, diagnosis: str, symptoms: List[str], treatment: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация клинической согласованности диагноза, симптомов и лечения"""
        symptoms_text = ", ".join(symptoms) if symptoms else "не указаны"
        treatment_text = json.dumps(treatment, ensure_ascii=False) if treatment else "не указано"
        
        prompt = f"""
        Проверьте клиническую согласованность диагноза, симптомов и лечения:
        
        ДИАГНОЗ: {diagnosis}
        СИМПТОМЫ: {symptoms_text}
        ЛЕЧЕНИЕ: {treatment_text}
        
        Предоставьте валидацию согласованности в формате JSON:
        {{
            "consistency_assessment": {{
                "overall_consistency": "высокая/средняя/низкая/несогласованная",
                "consistency_score": "оценка согласованности от 1 до 10",
                "clinical_logic": "логичность клинического мышления",
                "evidence_support": "поддержка доказательствами",
                "guideline_adherence": "соответствие клиническим рекомендациям"
            }},
            "diagnosis_validation": {{
                "diagnosis_accuracy": "точность диагноза",
                "symptom_alignment": {{
                    "supporting_symptoms": ["поддерживающий симптом 1", "поддерживающий симптом 2"],
                    "contradicting_symptoms": ["противоречащий симптом 1", "противоречащий симптом 2"],
                    "missing_key_symptoms": ["отсутствующий ключевой симптом 1", "отсутствующий ключевой симптом 2"],
                    "alignment_percentage": "процент соответствия симптомов"
                }},
                "differential_diagnosis": {{
                    "alternative_diagnoses": ["альтернативный диагноз 1", "альтернативный диагноз 2"],
                    "ruling_out_rationale": "обоснование исключения альтернатив",
                    "additional_tests_needed": ["дополнительный тест 1", "дополнительный тест 2"]
                }}
            }},
            "treatment_validation": {{
                "treatment_appropriateness": "соответствие лечения диагнозу",
                "medication_analysis": [
                    {{
                        "medication": "препарат",
                        "indication_match": "соответствие показаниям",
                        "dosage_appropriateness": "соответствие дозировки",
                        "contraindication_check": "проверка противопоказаний",
                        "interaction_risks": ["риск взаимодействия 1", "риск взаимодействия 2"]
                    }}
                ],
                "non_pharmacological_interventions": [
                    {{
                        "intervention": "немедикаментозное вмешательство",
                        "evidence_base": "доказательная база",
                        "appropriateness": "соответствие состоянию",
                        "expected_outcome": "ожидаемый результат"
                    }}
                ]
            }},
            "clinical_red_flags": [
                {{
                    "red_flag": "тревожный признак",
                    "category": "диагноз/симптомы/лечение",
                    "severity": "критический/высокий/средний/низкий",
                    "clinical_significance": "клиническая значимость",
                    "recommended_action": "рекомендуемое действие",
                    "urgency": "срочность действия"
                }}
            ],
            "evidence_gaps": [
                {{
                    "gap": "пробел в доказательствах",
                    "area": "область пробела",
                    "impact": "влияние на лечение",
                    "suggested_investigation": "предлагаемое исследование",
                    "priority": "приоритет устранения"
                }}
            ],
            "quality_indicators": {{
                "diagnostic_accuracy_indicators": ["индикатор точности диагностики 1", "индикатор точности диагностики 2"],
                "treatment_quality_indicators": ["индикатор качества лечения 1", "индикатор качества лечения 2"],
                "patient_safety_indicators": ["индикатор безопасности 1", "индикатор безопасности 2"],
                "outcome_predictors": ["предиктор исхода 1", "предиктор исхода 2"]
            }},
            "improvement_recommendations": [
                {{
                    "area": "область улучшения",
                    "recommendation": "рекомендация",
                    "rationale": "обоснование",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_steps": ["шаг внедрения 1", "шаг внедрения 2"]
                }}
            ],
            "follow_up_requirements": {{
                "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                "follow_up_timeline": "график наблюдения",
                "reassessment_triggers": ["триггер переоценки 1", "триггер переоценки 2"],
                "specialist_referral_indications": ["показание к консультации 1", "показание к консультации 2"]
            }}
        }}
        """
        
        system_prompt = """Вы клинический эксперт с глубокими знаниями в области диагностики и лечения заболеваний.
        Анализируете клиническую согласованность диагнозов, симптомов и назначенного лечения.
        Используете принципы доказательной медицины и современные клинические рекомендации.
        Выявляете потенциальные проблемы безопасности и качества медицинской помощи.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=3500
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
    
    async def audit_prescription_safety(self, prescriptions: List[Dict], patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Аудит безопасности назначений и рецептов"""
        prescriptions_text = "\n".join([
            f"- {p.get('medication', 'не указано')}: {p.get('dosage', 'не указано')}, {p.get('frequency', 'не указано')}, {p.get('duration', 'не указано')}"
            for p in prescriptions[:10]  # Ограничиваем для анализа
        ])
        
        patient_text = json.dumps(patient_profile, ensure_ascii=False, indent=2)
        
        prompt = f"""
        Проведите аудит безопасности назначений и рецептов:
        
        НАЗНАЧЕНИЯ:
        {prescriptions_text}
        
        ПРОФИЛЬ ПАЦИЕНТА:
        {patient_text}
        
        Предоставьте аудит безопасности в формате JSON:
        {{
            "safety_assessment": {{
                "overall_safety_score": "общая оценка безопасности от 1 до 10",
                "prescriptions_reviewed": {len(prescriptions)},
                "high_risk_prescriptions": "количество высокорисковых назначений",
                "safety_alerts": "количество предупреждений безопасности",
                "critical_interactions": "количество критических взаимодействий"
            }},
            "medication_analysis": [
                {{
                    "medication": "название препарата",
                    "safety_profile": {{
                        "risk_category": "низкий/средний/высокий/критический",
                        "contraindications": ["противопоказание 1", "противопоказание 2"],
                        "patient_specific_risks": ["специфический риск 1", "специфический риск 2"],
                        "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"]
                    }},
                    "dosage_assessment": {{
                        "appropriateness": "соответствие дозировки",
                        "age_adjustment": "коррекция по возрасту",
                        "renal_adjustment": "коррекция по функции почек",
                        "hepatic_adjustment": "коррекция по функции печени",
                        "weight_based_dosing": "дозирование по весу"
                    }},
                    "administration_safety": {{
                        "route_appropriateness": "соответствие пути введения",
                        "frequency_validation": "валидация частоты приема",
                        "duration_assessment": "оценка длительности курса",
                        "timing_considerations": ["соображение по времени 1", "соображение по времени 2"]
                    }}
                }}
            ],
            "drug_interactions": [
                {{
                    "interaction_type": "тип взаимодействия",
                    "medications_involved": ["препарат 1", "препарат 2"],
                    "severity": "критическая/высокая/средняя/низкая",
                    "mechanism": "механизм взаимодействия",
                    "clinical_significance": "клиническая значимость",
                    "management_strategy": "стратегия управления",
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
                }}
            ],
            "patient_specific_considerations": {{
                "age_related_factors": [
                    {{
                        "factor": "возрастной фактор",
                        "impact": "влияние на назначения",
                        "recommendations": ["рекомендация 1", "рекомендация 2"]
                    }}
                ],
                "comorbidity_interactions": [
                    {{
                        "comorbidity": "сопутствующее заболевание",
                        "affected_medications": ["затронутый препарат 1", "затронутый препарат 2"],
                        "risk_assessment": "оценка риска",
                        "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
                    }}
                ],
                "allergy_considerations": [
                    {{
                        "allergen": "аллерген",
                        "cross_reactivity": "перекрестная реактивность",
                        "alternative_options": ["альтернативный вариант 1", "альтернативный вариант 2"],
                        "emergency_protocols": ["протокол экстренной помощи 1", "протокол экстренной помощи 2"]
                    }}
                ]
            }},
            "safety_alerts": [
                {{
                    "alert_type": "тип предупреждения",
                    "severity": "критическое/высокое/среднее/низкое",
                    "description": "описание предупреждения",
                    "affected_prescription": "затронутое назначение",
                    "recommended_action": "рекомендуемое действие",
                    "urgency": "срочность",
                    "follow_up_required": "требуется ли наблюдение"
                }}
            ],
            "compliance_assessment": {{
                "regulatory_compliance": {{
                    "prescription_format": "соответствие формата рецепта",
                    "required_information": "наличие обязательной информации",
                    "signature_requirements": "требования к подписям",
                    "controlled_substances": "контролируемые вещества"
                }},
                "clinical_guidelines": {{
                    "guideline_adherence": "соответствие клиническим рекомендациям",
                    "evidence_based_prescribing": "назначения на основе доказательств",
                    "first_line_therapy": "терапия первой линии",
                    "rational_prescribing": "рациональное назначение"
                }}
            }},
            "monitoring_recommendations": [
                {{
                    "medication": "препарат для мониторинга",
                    "parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "frequency": "частота мониторинга",
                    "baseline_requirements": ["базовое требование 1", "базовое требование 2"],
                    "alert_values": ["пороговое значение 1", "пороговое значение 2"],
                    "action_plan": "план действий при отклонениях"
                }}
            ],
            "optimization_opportunities": [
                {{
                    "opportunity": "возможность оптимизации",
                    "current_approach": "текущий подход",
                    "suggested_improvement": "предлагаемое улучшение",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_considerations": ["соображение внедрения 1", "соображение внедрения 2"]
                }}
            ],
            "patient_education_needs": [
                {{
                    "topic": "тема обучения пациента",
                    "key_points": ["ключевой момент 1", "ключевой момент 2"],
                    "safety_warnings": ["предупреждение безопасности 1", "предупреждение безопасности 2"],
                    "adherence_strategies": ["стратегия приверженности 1", "стратегия приверженности 2"]
                }}
            ]
        }}
        """
        
        system_prompt = """Вы клинический фармаколог с экспертизой в области безопасности лекарственных средств и рационального назначения.
        Проводите комплексный аудит назначений на предмет безопасности, эффективности и соответствия стандартам.
        Анализируете лекарственные взаимодействия, противопоказания и индивидуальные факторы риска пациента.
        Предоставляете практические рекомендации по оптимизации фармакотерапии и обеспечению безопасности пациентов.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4000
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

    async def analyze_medical_trends(self, medical_data: List[Dict], time_period: str, analysis_type: str) -> Dict[str, Any]:
        """Анализ медицинских трендов и паттернов в данных"""
        # Ограничиваем данные для анализа
        data_sample = medical_data[:100] if len(medical_data) > 100 else medical_data
        
        # Подготавливаем сводку данных
        data_summary = {
            "total_records": len(medical_data),
            "sample_size": len(data_sample),
            "time_period": time_period,
            "analysis_type": analysis_type,
            "data_types": list(set([record.get("type", "unknown") for record in data_sample])),
            "date_range": {
                "start": min([record.get("date", "2024-01-01") for record in data_sample]) if data_sample else "N/A",
                "end": max([record.get("date", "2024-01-01") for record in data_sample]) if data_sample else "N/A"
            }
        }
        
        sample_data_text = "\n".join([
            f"- {record.get('type', 'unknown')}: {record.get('diagnosis', 'N/A')} ({record.get('date', 'N/A')})"
            for record in data_sample[:20]  # Показываем только первые 20 записей
        ])
        
        prompt = f"""
        Проанализируйте медицинские тренды и паттерны в предоставленных данных:
        
        ПАРАМЕТРЫ АНАЛИЗА:
        - Период анализа: {time_period}
        - Тип анализа: {analysis_type}
        - Общее количество записей: {data_summary['total_records']}
        - Размер выборки: {data_summary['sample_size']}
        
        ОБРАЗЕЦ ДАННЫХ:
        {sample_data_text}
        
        СВОДКА ДАННЫХ: {json.dumps(data_summary, ensure_ascii=False)}
        
        Предоставьте комплексный анализ трендов в формате JSON:
        {{
            "trend_analysis": {{
                "overall_trends": [
                    {{
                        "trend": "название тренда",
                        "direction": "возрастающий/убывающий/стабильный",
                        "magnitude": "сильный/умеренный/слабый",
                        "confidence": "высокая/средняя/низкая",
                        "time_pattern": "сезонный/циклический/линейный",
                        "statistical_significance": "значимый/незначимый",
                        "clinical_relevance": "высокая/средняя/низкая"
                    }}
                ],
                "seasonal_patterns": [
                    {{
                        "pattern": "сезонный паттерн",
                        "season": "весна/лето/осень/зима",
                        "peak_months": ["месяц 1", "месяц 2"],
                        "intensity": "высокая/средняя/низкая",
                        "recurrence": "ежегодно/периодически/однократно",
                        "affected_conditions": ["состояние 1", "состояние 2"]
                    }}
                ],
                "demographic_trends": [
                    {{
                        "demographic": "возрастная группа/пол/регион",
                        "trend_description": "описание тренда",
                        "growth_rate": "процент изменения",
                        "risk_factors": ["фактор риска 1", "фактор риска 2"],
                        "prevention_opportunities": ["возможность профилактики 1", "возможность профилактики 2"]
                    }}
                ]
            }},
            "pattern_detection": {{
                "disease_patterns": [
                    {{
                        "disease": "заболевание",
                        "pattern_type": "эпидемический/эндемический/спорадический",
                        "frequency": "частота встречаемости",
                        "geographic_distribution": "географическое распределение",
                        "age_distribution": "возрастное распределение",
                        "comorbidity_patterns": ["сопутствующее заболевание 1", "сопутствующее заболевание 2"],
                        "treatment_patterns": ["паттерн лечения 1", "паттерн лечения 2"]
                    }}
                ],
                "treatment_effectiveness": [
                    {{
                        "treatment": "метод лечения",
                        "effectiveness_trend": "улучшается/ухудшается/стабильно",
                        "success_rate": "процент успеха",
                        "response_time": "время ответа на лечение",
                        "side_effects_trend": "увеличиваются/уменьшаются/стабильны",
                        "cost_effectiveness": "экономическая эффективность"
                    }}
                ],
                "resource_utilization": [
                    {{
                        "resource": "тип ресурса",
                        "utilization_trend": "увеличивается/уменьшается/стабильно",
                        "peak_usage_times": ["время пика 1", "время пика 2"],
                        "bottlenecks": ["узкое место 1", "узкое место 2"],
                        "optimization_opportunities": ["возможность оптимизации 1", "возможность оптимизации 2"]
                    }}
                ]
            }},
            "predictive_insights": {{
                "short_term_predictions": [
                    {{
                        "prediction": "краткосрочный прогноз",
                        "timeframe": "временные рамки",
                        "probability": "вероятность",
                        "impact": "влияние",
                        "confidence_interval": "доверительный интервал",
                        "key_indicators": ["индикатор 1", "индикатор 2"]
                    }}
                ],
                "long_term_forecasts": [
                    {{
                        "forecast": "долгосрочный прогноз",
                        "timeframe": "временные рамки",
                        "scenario": "оптимистичный/реалистичный/пессимистичный",
                        "assumptions": ["предположение 1", "предположение 2"],
                        "potential_interventions": ["вмешательство 1", "вмешательство 2"]
                    }}
                ],
                "risk_projections": [
                    {{
                        "risk": "прогнозируемый риск",
                        "probability": "вероятность реализации",
                        "timeline": "временные рамки",
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "monitoring_indicators": ["индикатор мониторинга 1", "индикатор мониторинга 2"]
                    }}
                ]
            }},
            "quality_metrics": {{
                "data_quality_assessment": {{
                    "completeness": "процент полноты данных",
                    "accuracy": "оценка точности",
                    "consistency": "оценка согласованности",
                    "timeliness": "оценка своевременности",
                    "reliability": "оценка надежности"
                }},
                "analysis_confidence": {{
                    "statistical_power": "статистическая мощность",
                    "sample_representativeness": "представительность выборки",
                    "bias_assessment": "оценка смещений",
                    "uncertainty_factors": ["фактор неопределенности 1", "фактор неопределенности 2"]
                }}
            }},
            "actionable_recommendations": [
                {{
                    "recommendation": "практическая рекомендация",
                    "priority": "высокий/средний/низкий",
                    "implementation_complexity": "сложность внедрения",
                    "expected_impact": "ожидаемое влияние",
                    "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                    "timeline": "временные рамки внедрения",
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"],
                    "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                }}
            ],
            "visualization_suggestions": [
                {{
                    "chart_type": "тип диаграммы",
                    "data_focus": "фокус данных",
                    "key_insights": ["ключевой инсайт 1", "ключевой инсайт 2"],
                    "interactive_elements": ["интерактивный элемент 1", "интерактивный элемент 2"]
                }}
            ]
        }}
        """
        
        system_prompt = """Вы эксперт по медицинской аналитике и анализу данных с глубокими знаниями в области эпидемиологии, биостатистики и здравоохранения.
        Анализируете медицинские тренды, выявляете паттерны и предоставляете практические инсайты для улучшения качества медицинской помощи.
        Используете современные методы анализа данных и машинного обучения для выявления скрытых закономерностей.
        Предоставляете статистически обоснованные выводы с учетом клинической значимости.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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
    
    async def detect_anomalies(self, dataset: List[Dict], baseline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Выявление аномалий в медицинских данных"""
        # Ограничиваем данные для анализа
        data_sample = dataset[:50] if len(dataset) > 50 else dataset
        
        dataset_summary = {
            "total_records": len(dataset),
            "sample_size": len(data_sample),
            "data_fields": list(set().union(*[record.keys() for record in data_sample])) if data_sample else [],
            "record_types": list(set([record.get("type", "unknown") for record in data_sample]))
        }
        
        sample_text = "\n".join([
            f"- Record {i+1}: {json.dumps(record, ensure_ascii=False)}"
            for i, record in enumerate(data_sample[:10])
        ])
        
        baseline_text = json.dumps(baseline_data, ensure_ascii=False, indent=2)
        
        prompt = f"""
        Выявите аномалии в медицинских данных по сравнению с базовыми показателями:
        
        БАЗОВЫЕ ДАННЫЕ:
        {baseline_text}
        
        АНАЛИЗИРУЕМЫЙ ДАТАСЕТ:
        Общее количество записей: {dataset_summary['total_records']}
        Размер выборки: {dataset_summary['sample_size']}
        Типы записей: {dataset_summary['record_types']}
        
        ОБРАЗЕЦ ДАННЫХ:
        {sample_text}
        
        Предоставьте анализ аномалий в формате JSON:
        {{
            "anomaly_detection": {{
                "detection_summary": {{
                    "total_anomalies": "количество выявленных аномалий",
                    "anomaly_rate": "процент аномальных записей",
                    "severity_distribution": {{
                        "critical": "количество критических аномалий",
                        "high": "количество высокоприоритетных аномалий",
                        "medium": "количество среднеприоритетных аномалий",
                        "low": "количество низкоприоритетных аномалий"
                    }},
                    "detection_confidence": "уровень уверенности в детекции"
                }},
                "statistical_anomalies": [
                    {{
                        "field": "поле данных",
                        "anomaly_type": "выброс/тренд/паттерн",
                        "description": "описание аномалии",
                        "baseline_value": "базовое значение",
                        "observed_value": "наблюдаемое значение",
                        "deviation": "степень отклонения",
                        "statistical_significance": "статистическая значимость",
                        "z_score": "z-оценка",
                        "p_value": "p-значение"
                    }}
                ],
                "clinical_anomalies": [
                    {{
                        "anomaly": "клиническая аномалия",
                        "clinical_significance": "клиническая значимость",
                        "patient_safety_impact": "влияние на безопасность пациента",
                        "frequency": "частота встречаемости",
                        "associated_conditions": ["связанное состояние 1", "связанное состояние 2"],
                        "investigation_priority": "приоритет расследования",
                        "recommended_actions": ["рекомендуемое действие 1", "рекомендуемое действие 2"]
                    }}
                ],
                "temporal_anomalies": [
                    {{
                        "time_period": "временной период",
                        "anomaly_description": "описание временной аномалии",
                        "expected_pattern": "ожидаемый паттерн",
                        "observed_pattern": "наблюдаемый паттерн",
                        "seasonal_adjustment": "сезонная корректировка",
                        "trend_deviation": "отклонение от тренда",
                        "cyclical_analysis": "циклический анализ"
                    }}
                ]
            }},
            "root_cause_analysis": [
                {{
                    "anomaly": "аномалия для анализа",
                    "potential_causes": [
                        {{
                            "cause": "потенциальная причина",
                            "probability": "вероятность",
                            "evidence": ["доказательство 1", "доказательство 2"],
                            "impact_assessment": "оценка влияния",
                            "verification_methods": ["метод проверки 1", "метод проверки 2"]
                        }}
                    ],
                    "contributing_factors": ["способствующий фактор 1", "способствующий фактор 2"],
                    "system_factors": ["системный фактор 1", "системный фактор 2"],
                    "human_factors": ["человеческий фактор 1", "человеческий фактор 2"]
                }}
            ],
            "impact_assessment": {{
                "patient_impact": [
                    {{
                        "impact_type": "тип влияния на пациента",
                        "severity": "тяжесть",
                        "affected_population": "затронутая популяция",
                        "immediate_risks": ["немедленный риск 1", "немедленный риск 2"],
                        "long_term_consequences": ["долгосрочное последствие 1", "долгосрочное последствие 2"]
                    }}
                ],
                "operational_impact": [
                    {{
                        "area": "операционная область",
                        "impact_description": "описание влияния",
                        "resource_implications": ["влияние на ресурсы 1", "влияние на ресурсы 2"],
                        "workflow_disruption": "нарушение рабочего процесса",
                        "cost_implications": "финансовые последствия"
                    }}
                ],
                "quality_impact": [
                    {{
                        "quality_metric": "метрика качества",
                        "baseline_performance": "базовая производительность",
                        "current_performance": "текущая производительность",
                        "performance_gap": "разрыв в производительности",
                        "improvement_potential": "потенциал улучшения"
                    }}
                ]
            }},
            "corrective_actions": [
                {{
                    "action": "корректирующее действие",
                    "urgency": "срочность",
                    "responsible_party": "ответственная сторона",
                    "implementation_timeline": "график внедрения",
                    "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"],
                    "monitoring_plan": "план мониторинга",
                    "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                }}
            ],
            "prevention_strategies": [
                {{
                    "strategy": "стратегия предотвращения",
                    "target_anomaly_type": "тип целевой аномалии",
                    "implementation_approach": "подход к внедрению",
                    "early_warning_indicators": ["индикатор раннего предупреждения 1", "индикатор раннего предупреждения 2"],
                    "monitoring_frequency": "частота мониторинга",
                    "alert_thresholds": ["пороговое значение 1", "пороговое значение 2"]
                }}
            ],
            "continuous_monitoring": {{
                "monitoring_framework": {{
                    "key_metrics": ["ключевая метрика 1", "ключевая метрика 2"],
                    "data_sources": ["источник данных 1", "источник данных 2"],
                    "analysis_frequency": "частота анализа",
                    "reporting_schedule": "график отчетности",
                    "escalation_procedures": ["процедура эскалации 1", "процедура эскалации 2"]
                }},
                "automated_detection": {{
                    "algorithm_recommendations": ["рекомендация алгоритма 1", "рекомендация алгоритма 2"],
                    "threshold_settings": ["настройка порога 1", "настройка порога 2"],
                    "false_positive_management": "управление ложными срабатываниями",
                    "model_updating_strategy": "стратегия обновления модели"
                }}
            }}
        }}
        """
        
        system_prompt = """Вы специалист по выявлению аномалий в медицинских данных с экспертизой в области статистического анализа и машинного обучения.
        Анализируете медицинские данные для выявления отклонений от нормы, статистических выбросов и необычных паттернов.
        Оцениваете клиническую значимость аномалий и их влияние на безопасность пациентов и качество медицинской помощи.
        Предоставляете практические рекомендации по корректирующим действиям и предотвращению аномалий.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4000
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
    
    async def predict_outcomes(self, patient_data: Dict[str, Any], historical_outcomes: List[Dict]) -> Dict[str, Any]:
        """Прогнозирование медицинских исходов на основе данных"""
        patient_text = json.dumps(patient_data, ensure_ascii=False, indent=2)
        
        # Ограничиваем исторические данные
        outcomes_sample = historical_outcomes[:30] if len(historical_outcomes) > 30 else historical_outcomes
        outcomes_summary = {
            "total_cases": len(historical_outcomes),
            "sample_size": len(outcomes_sample),
            "outcome_types": list(set([outcome.get("result", "unknown") for outcome in outcomes_sample])),
            "success_rate": len([o for o in outcomes_sample if o.get("result") == "success"]) / len(outcomes_sample) * 100 if outcomes_sample else 0
        }
        
        outcomes_text = "\n".join([
            f"- Case {i+1}: {outcome.get('condition', 'N/A')} → {outcome.get('result', 'N/A')} (duration: {outcome.get('duration', 'N/A')})"
            for i, outcome in enumerate(outcomes_sample[:15])
        ])
        
        prompt = f"""
        Спрогнозируйте медицинские исходы для пациента на основе исторических данных:
        
        ДАННЫЕ ПАЦИЕНТА:
        {patient_text}
        
        ИСТОРИЧЕСКИЕ ИСХОДЫ:
        Общее количество случаев: {outcomes_summary['total_cases']}
        Размер выборки: {outcomes_summary['sample_size']}
        Типы исходов: {outcomes_summary['outcome_types']}
        Общий процент успеха: {outcomes_summary['success_rate']:.1f}%
        
        ОБРАЗЕЦ ИСТОРИЧЕСКИХ СЛУЧАЕВ:
        {outcomes_text}
        
        Предоставьте прогноз исходов в формате JSON:
        {{
            "outcome_predictions": {{
                "primary_prediction": {{
                    "predicted_outcome": "основной прогнозируемый исход",
                    "probability": "вероятность в процентах",
                    "confidence_level": "уровень уверенности",
                    "time_to_outcome": "время до исхода",
                    "key_factors": ["ключевой фактор 1", "ключевой фактор 2"],
                    "risk_stratification": "низкий/средний/высокий риск"
                }},
                "alternative_scenarios": [
                    {{
                        "scenario": "альтернативный сценарий",
                        "probability": "вероятность",
                        "conditions": ["условие 1", "условие 2"],
                        "timeline": "временные рамки",
                        "intervention_requirements": ["требуемое вмешательство 1", "требуемое вмешательство 2"]
                    }}
                ],
                "worst_case_scenario": {{
                    "outcome": "наихудший исход",
                    "probability": "вероятность",
                    "warning_signs": ["предупреждающий знак 1", "предупреждающий знак 2"],
                    "prevention_strategies": ["стратегия предотвращения 1", "стратегия предотвращения 2"],
                    "emergency_protocols": ["протокол экстренной помощи 1", "протокол экстренной помощи 2"]
                }},
                "best_case_scenario": {{
                    "outcome": "наилучший исход",
                    "probability": "вероятность",
                    "success_factors": ["фактор успеха 1", "фактор успеха 2"],
                    "optimization_strategies": ["стратегия оптимизации 1", "стратегия оптимизации 2"],
                    "maintenance_requirements": ["требование поддержания 1", "требование поддержания 2"]
                }}
            }},
            "prognostic_factors": {{
                "positive_prognostic_factors": [
                    {{
                        "factor": "положительный прогностический фактор",
                        "impact_strength": "сильное/умеренное/слабое влияние",
                        "evidence_level": "уровень доказательности",
                        "modifiability": "модифицируемый/немодифицируемый",
                        "optimization_potential": "потенциал оптимизации"
                    }}
                ],
                "negative_prognostic_factors": [
                    {{
                        "factor": "отрицательный прогностический фактор",
                        "risk_magnitude": "величина риска",
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"],
                        "intervention_timing": "время вмешательства"
                    }}
                ],
                "neutral_factors": [
                    {{
                        "factor": "нейтральный фактор",
                        "monitoring_value": "ценность мониторинга",
                        "potential_changes": ["потенциальное изменение 1", "потенциальное изменение 2"]
                    }}
                ]
            }},
            "treatment_response_prediction": {{
                "expected_response": {{
                    "response_type": "тип ответа на лечение",
                    "response_timeline": "временные рамки ответа",
                    "response_magnitude": "величина ответа",
                    "response_durability": "длительность ответа",
                    "side_effect_profile": "профиль побочных эффектов"
                }},
                "treatment_modifications": [
                    {{
                        "modification": "модификация лечения",
                        "indication": "показание для модификации",
                        "expected_benefit": "ожидаемая польза",
                        "implementation_timing": "время внедрения",
                        "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
                    }}
                ],
                "resistance_patterns": [
                    {{
                        "resistance_type": "тип резистентности",
                        "probability": "вероятность развития",
                        "early_indicators": ["ранний индикатор 1", "ранний индикатор 2"],
                        "management_strategies": ["стратегия управления 1", "стратегия управления 2"]
                    }}
                ]
            }},
            "quality_of_life_prediction": {{
                "functional_outcomes": [
                    {{
                        "domain": "функциональная область",
                        "predicted_level": "прогнозируемый уровень",
                        "improvement_potential": "потенциал улучшения",
                        "rehabilitation_needs": ["потребность в реабилитации 1", "потребность в реабилитации 2"],
                        "adaptive_strategies": ["адаптивная стратегия 1", "адаптивная стратегия 2"]
                    }}
                ],
                "psychosocial_outcomes": [
                    {{
                        "aspect": "психосоциальный аспект",
                        "predicted_impact": "прогнозируемое влияние",
                        "support_needs": ["потребность в поддержке 1", "потребность в поддержке 2"],
                        "coping_strategies": ["стратегия совладания 1", "стратегия совладания 2"]
                    }}
                ]
            }},
            "long_term_prognosis": {{
                "5_year_outlook": {{
                    "survival_probability": "вероятность выживания",
                    "disease_progression": "прогрессирование заболевания",
                    "functional_status": "функциональный статус",
                    "quality_of_life": "качество жизни",
                    "care_requirements": ["требование к уходу 1", "требование к уходу 2"]
                }},
                "10_year_outlook": {{
                    "survival_probability": "вероятность выживания",
                    "disease_progression": "прогрессирование заболевания",
                    "functional_status": "функциональный статус",
                    "quality_of_life": "качество жизни",
                    "care_requirements": ["требование к уходу 1", "требование к уходу 2"]
                }},
                "lifetime_considerations": [
                    {{
                        "consideration": "пожизненное соображение",
                        "impact": "влияние",
                        "management_approach": "подход к управлению",
                        "family_implications": ["влияние на семью 1", "влияние на семью 2"]
                    }}
                ]
            }},
            "monitoring_recommendations": {{
                "immediate_monitoring": [
                    {{
                        "parameter": "параметр немедленного мониторинга",
                        "frequency": "частота",
                        "alert_thresholds": ["пороговое значение 1", "пороговое значение 2"],
                        "action_triggers": ["триггер действия 1", "триггер действия 2"]
                    }}
                ],
                "long_term_surveillance": [
                    {{
                        "surveillance_type": "тип долгосрочного наблюдения",
                        "schedule": "график",
                        "key_indicators": ["ключевой индикатор 1", "ключевой индикатор 2"],
                        "screening_protocols": ["протокол скрининга 1", "протокол скрининга 2"]
                    }}
                ]
            }},
            "uncertainty_analysis": {{
                "confidence_intervals": [
                    {{
                        "prediction": "прогноз",
                        "lower_bound": "нижняя граница",
                        "upper_bound": "верхняя граница",
                        "confidence_level": "уровень доверия"
                    }}
                ],
                "sensitivity_analysis": [
                    {{
                        "variable": "переменная",
                        "impact_on_prediction": "влияние на прогноз",
                        "uncertainty_contribution": "вклад в неопределенность"
                    }}
                ],
                "model_limitations": ["ограничение модели 1", "ограничение модели 2"],
                "data_quality_factors": ["фактор качества данных 1", "фактор качества данных 2"]
            }}
        }}
        """
        
        system_prompt = """Вы эксперт по прогнозированию медицинских исходов с глубокими знаниями в области клинической медицины, биостатистики и прогностического моделирования.
        Анализируете данные пациентов и исторические исходы для создания точных и клинически значимых прогнозов.
        Учитываете множественные факторы риска, коморбидности и индивидуальные особенности пациентов.
        Предоставляете вероятностные оценки с указанием уровня уверенности и клинических рекомендаций.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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
    
    async def generate_insights_report(self, analytics_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """Генерация отчета с аналитическими инсайтами"""
        analytics_text = json.dumps(analytics_data, ensure_ascii=False, indent=2)
        
        prompt = f"""
        Сгенерируйте комплексный отчет с аналитическими инсайтами на основе предоставленных данных:
        
        ТИП ОТЧЕТА: {report_type}
        
        АНАЛИТИЧЕСКИЕ ДАННЫЕ:
        {analytics_text}
        
        Создайте структурированный отчет в формате JSON:
        {{
            "executive_summary": {{
                "report_title": "название отчета",
                "report_period": "период отчета",
                "key_findings": [
                    {{
                        "finding": "ключевая находка",
                        "significance": "значимость",
                        "impact": "влияние",
                        "confidence": "уровень уверенности"
                    }}
                ],
                "critical_insights": [
                    {{
                        "insight": "критический инсайт",
                        "implication": "последствие",
                        "urgency": "срочность",
                        "recommended_action": "рекомендуемое действие"
                    }}
                ],
                "overall_assessment": "общая оценка ситуации",
                "strategic_recommendations": ["стратегическая рекомендация 1", "стратегическая рекомендация 2"]
            }},
            "detailed_analysis": {{
                "performance_metrics": [
                    {{
                        "metric": "показатель производительности",
                        "current_value": "текущее значение",
                        "benchmark": "эталонное значение",
                        "trend": "тренд",
                        "variance_analysis": "анализ отклонений",
                        "improvement_opportunities": ["возможность улучшения 1", "возможность улучшения 2"]
                    }}
                ],
                "comparative_analysis": [
                    {{
                        "comparison_dimension": "измерение сравнения",
                        "baseline": "базовая линия",
                        "current_state": "текущее состояние",
                        "performance_gap": "разрыв в производительности",
                        "root_causes": ["основная причина 1", "основная причина 2"],
                        "corrective_actions": ["корректирующее действие 1", "корректирующее действие 2"]
                    }}
                ],
                "trend_analysis": [
                    {{
                        "trend": "тренд",
                        "direction": "направление",
                        "velocity": "скорость изменения",
                        "sustainability": "устойчивость",
                        "influencing_factors": ["влияющий фактор 1", "влияющий фактор 2"],
                        "projection": "прогноз"
                    }}
                ]
            }},
            "clinical_insights": {{
                "patient_outcomes": [
                    {{
                        "outcome_category": "категория исхода",
                        "performance_indicator": "индикатор производительности",
                        "clinical_significance": "клиническая значимость",
                        "quality_impact": "влияние на качество",
                        "safety_implications": ["влияние на безопасность 1", "влияние на безопасность 2"],
                        "improvement_strategies": ["стратегия улучшения 1", "стратегия улучшения 2"]
                    }}
                ],
                "care_quality_indicators": [
                    {{
                        "indicator": "индикатор качества помощи",
                        "measurement": "измерение",
                        "target": "целевое значение",
                        "achievement": "достижение",
                        "gap_analysis": "анализ пробелов",
                        "quality_initiatives": ["инициатива качества 1", "инициатива качества 2"]
                    }}
                ],
                "patient_safety_metrics": [
                    {{
                        "safety_metric": "метрика безопасности",
                        "incident_rate": "частота инцидентов",
                        "severity_distribution": "распределение по тяжести",
                        "prevention_effectiveness": "эффективность предотвращения",
                        "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                    }}
                ]
            }},
            "operational_insights": {{
                "resource_utilization": [
                    {{
                        "resource": "ресурс",
                        "utilization_rate": "коэффициент использования",
                        "efficiency_score": "оценка эффективности",
                        "bottlenecks": ["узкое место 1", "узкое место 2"],
                        "optimization_potential": "потенциал оптимизации",
                        "capacity_planning": ["планирование мощности 1", "планирование мощности 2"]
                    }}
                ],
                "workflow_analysis": [
                    {{
                        "process": "процесс",
                        "cycle_time": "время цикла",
                        "throughput": "пропускная способность",
                        "quality_metrics": ["метрика качества 1", "метрика качества 2"],
                        "improvement_areas": ["область улучшения 1", "область улучшения 2"],
                        "automation_opportunities": ["возможность автоматизации 1", "возможность автоматизации 2"]
                    }}
                ],
                "cost_effectiveness": [
                    {{
                        "cost_center": "центр затрат",
                        "cost_per_unit": "стоимость за единицу",
                        "value_delivered": "доставленная ценность",
                        "roi_analysis": "анализ ROI",
                        "cost_optimization": ["оптимизация затрат 1", "оптимизация затрат 2"],
                        "investment_priorities": ["приоритет инвестиций 1", "приоритет инвестиций 2"]
                    }}
                ]
            }},
            "predictive_insights": {{
                "forecasting_models": [
                    {{
                        "model": "прогностическая модель",
                        "prediction_horizon": "горизонт прогнозирования",
                        "accuracy_metrics": "метрики точности",
                        "key_variables": ["ключевая переменная 1", "ключевая переменная 2"],
                        "scenario_analysis": ["анализ сценария 1", "анализ сценария 2"],
                        "confidence_intervals": "доверительные интервалы"
                    }}
                ],
                "risk_predictions": [
                    {{
                        "risk_category": "категория риска",
                        "probability": "вероятность",
                        "impact_assessment": "оценка влияния",
                        "early_warning_indicators": ["индикатор раннего предупреждения 1", "индикатор раннего предупреждения 2"],
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "contingency_plans": ["план на случай непредвиденных обстоятельств 1", "план на случай непредвиденных обстоятельств 2"]
                    }}
                ]
            }},
            "actionable_recommendations": {{
                "immediate_actions": [
                    {{
                        "action": "немедленное действие",
                        "priority": "приоритет",
                        "responsible_party": "ответственная сторона",
                        "timeline": "временные рамки",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                        "success_metrics": ["метрика успеха 1", "метрика успеха 2"],
                        "risk_assessment": "оценка риска"
                    }}
                ],
                "short_term_initiatives": [
                    {{
                        "initiative": "краткосрочная инициатива",
                        "objective": "цель",
                        "implementation_plan": "план внедрения",
                        "expected_outcomes": ["ожидаемый результат 1", "ожидаемый результат 2"],
                        "key_milestones": ["ключевая веха 1", "ключевая веха 2"],
                        "monitoring_framework": "система мониторинга"
                    }}
                ],
                "long_term_strategies": [
                    {{
                        "strategy": "долгосрочная стратегия",
                        "strategic_goal": "стратегическая цель",
                        "implementation_roadmap": "дорожная карта внедрения",
                        "investment_requirements": ["требование к инвестициям 1", "требование к инвестициям 2"],
                        "expected_roi": "ожидаемый ROI",
                        "success_factors": ["фактор успеха 1", "фактор успеха 2"]
                    }}
                ]
            }},
            "quality_assurance": {{
                "data_quality_assessment": {{
                    "completeness": "полнота данных",
                    "accuracy": "точность данных",
                    "consistency": "согласованность данных",
                    "timeliness": "своевременность данных",
                    "reliability": "надежность данных"
                }},
                "analysis_limitations": [
                    {{
                        "limitation": "ограничение анализа",
                        "impact": "влияние на результаты",
                        "mitigation": "способ снижения влияния",
                        "future_improvements": ["будущее улучшение 1", "будущее улучшение 2"]
                    }}
                ],
                "confidence_assessment": {{
                    "overall_confidence": "общий уровень уверенности",
                    "high_confidence_findings": ["находка с высокой уверенностью 1", "находка с высокой уверенностью 2"],
                    "moderate_confidence_findings": ["находка со средней уверенностью 1", "находка со средней уверенностью 2"],
                    "low_confidence_findings": ["находка с низкой уверенностью 1", "находка с низкой уверенностью 2"],
                    "uncertainty_factors": ["фактор неопределенности 1", "фактор неопределенности 2"]
                }}
            }},
            "appendices": {{
                "methodology": {{
                    "analytical_approach": "аналитический подход",
                    "data_sources": ["источник данных 1", "источник данных 2"],
                    "statistical_methods": ["статистический метод 1", "статистический метод 2"],
                    "assumptions": ["предположение 1", "предположение 2"],
                    "validation_procedures": ["процедура валидации 1", "процедура валидации 2"]
                }},
                "glossary": [
                    {{
                        "term": "термин",
                        "definition": "определение"
                    }}
                ],
                "references": [
                    {{
                        "reference": "ссылка на источник",
                        "relevance": "актуальность для анализа"
                    }}
                ]
            }}
        }}
        """
        
        system_prompt = """Вы эксперт по созданию аналитических отчетов в здравоохранении с глубокими знаниями в области медицинской аналитики, управления качеством и стратегического планирования.
        Создаете комплексные, структурированные отчеты с практическими инсайтами и рекомендациями для руководства медицинских учреждений.
        Анализируете данные с точки зрения клинической эффективности, операционной эффективности и финансовой устойчивости.
        Предоставляете четкие, обоснованные выводы с указанием уровня уверенности и практических шагов для внедрения.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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
    
    async def identify_risk_patterns(self, population_data: List[Dict], risk_factors: List[str]) -> Dict[str, Any]:
        """Выявление паттернов рисков в популяционных данных"""
        # Ограничиваем данные для анализа
        data_sample = population_data[:100] if len(population_data) > 100 else population_data
        
        population_summary = {
            "total_population": len(population_data),
            "sample_size": len(data_sample),
            "age_groups": list(set([p.get("age_group", "unknown") for p in data_sample])),
            "gender_distribution": {
                "male": len([p for p in data_sample if p.get("gender") == "male"]),
                "female": len([p for p in data_sample if p.get("gender") == "female"])
            },
            "risk_factors_analyzed": risk_factors
        }
        
        sample_text = "\n".join([
            f"- Patient {i+1}: Age {p.get('age', 'N/A')}, Gender {p.get('gender', 'N/A')}, Conditions: {p.get('conditions', [])}"
            for i, p in enumerate(data_sample[:15])
        ])
        
        risk_factors_text = ", ".join(risk_factors)
        
        prompt = f"""
        Выявите паттерны рисков в популяционных медицинских данных:
        
        АНАЛИЗИРУЕМЫЕ ФАКТОРЫ РИСКА: {risk_factors_text}
        
        ПОПУЛЯЦИОННЫЕ ДАННЫЕ:
        Общая популяция: {population_summary['total_population']} человек
        Размер выборки: {population_summary['sample_size']} человек
        Возрастные группы: {population_summary['age_groups']}
        Распределение по полу: М={population_summary['gender_distribution']['male']}, Ж={population_summary['gender_distribution']['female']}
        
        ОБРАЗЕЦ ДАННЫХ:
        {sample_text}
        
        Предоставьте анализ паттернов рисков в формате JSON:
        {{
            "risk_pattern_analysis": {{
                "population_overview": {{
                    "total_analyzed": {population_summary['total_population']},
                    "high_risk_percentage": "процент высокого риска",
                    "moderate_risk_percentage": "процент умеренного риска",
                    "low_risk_percentage": "процент низкого риска",
                    "risk_distribution_trend": "тренд распределения рисков"
                }},
                "demographic_risk_patterns": [
                    {{
                        "demographic": "демографическая группа",
                        "risk_level": "уровень риска",
                        "prevalence": "распространенность",
                        "key_risk_factors": ["ключевой фактор риска 1", "ключевой фактор риска 2"],
                        "protective_factors": ["защитный фактор 1", "защитный фактор 2"],
                        "intervention_priorities": ["приоритет вмешательства 1", "приоритет вмешательства 2"]
                    }}
                ],
                "geographic_patterns": [
                    {{
                        "region": "регион",
                        "risk_concentration": "концентрация риска",
                        "environmental_factors": ["фактор окружающей среды 1", "фактор окружающей среды 2"],
                        "socioeconomic_influences": ["социально-экономическое влияние 1", "социально-экономическое влияние 2"],
                        "healthcare_access": "доступность медицинской помощи",
                        "targeted_interventions": ["целевое вмешательство 1", "целевое вмешательство 2"]
                    }}
                ]
            }},
            "risk_factor_analysis": [
                {{
                    "risk_factor": "фактор риска",
                    "population_prevalence": "распространенность в популяции",
                    "relative_risk": "относительный риск",
                    "attributable_risk": "атрибутивный риск",
                    "modifiability": "модифицируемость",
                    "intervention_effectiveness": "эффективность вмешательства",
                    "cost_benefit_ratio": "соотношение затрат и выгод",
                    "population_impact": "влияние на популяцию",
                    "synergistic_effects": [
                        {{
                            "interacting_factor": "взаимодействующий фактор",
                            "combined_effect": "комбинированный эффект",
                            "risk_amplification": "усиление риска"
                        }}
                    ]
                }}
            ],
            "temporal_patterns": {{
                "seasonal_variations": [
                    {{
                        "risk_factor": "фактор риска",
                        "seasonal_pattern": "сезонный паттерн",
                        "peak_periods": ["пиковый период 1", "пиковый период 2"],
                        "cyclical_trends": "циклические тренды",
                        "environmental_correlations": ["корреляция с окружающей средой 1", "корреляция с окружающей средой 2"]
                    }}
                ],
                "age_related_patterns": [
                    {{
                        "age_group": "возрастная группа",
                        "risk_trajectory": "траектория риска",
                        "critical_periods": ["критический период 1", "критический период 2"],
                        "developmental_factors": ["фактор развития 1", "фактор развития 2"],
                        "prevention_windows": ["окно профилактики 1", "окно профилактики 2"]
                    }}
                ],
                "cohort_effects": [
                    {{
                        "birth_cohort": "когорта рождения",
                        "unique_exposures": ["уникальное воздействие 1", "уникальное воздействие 2"],
                        "risk_profile": "профиль риска",
                        "long_term_implications": ["долгосрочное последствие 1", "долгосрочное последствие 2"]
                    }}
                ]
            }},
            "clustering_analysis": {{
                "risk_clusters": [
                    {{
                        "cluster_id": "идентификатор кластера",
                        "cluster_characteristics": "характеристики кластера",
                        "population_size": "размер популяции",
                        "dominant_risk_factors": ["доминирующий фактор риска 1", "доминирующий фактор риска 2"],
                        "cluster_stability": "стабильность кластера",
                        "intervention_strategies": ["стратегия вмешательства 1", "стратегия вмешательства 2"]
                    }}
                ],
                "outlier_populations": [
                    {{
                        "population": "популяция-выброс",
                        "unique_characteristics": ["уникальная характеристика 1", "уникальная характеристика 2"],
                        "risk_anomalies": ["аномалия риска 1", "аномалия риска 2"],
                        "special_considerations": ["особое соображение 1", "особое соображение 2"]
                    }}
                ]
            }},
            "predictive_modeling": {{
                "risk_prediction_models": [
                    {{
                        "model_type": "тип модели",
                        "predictive_accuracy": "точность прогнозирования",
                        "key_predictors": ["ключевой предиктор 1", "ключевой предиктор 2"],
                        "model_validation": "валидация модели",
                        "clinical_utility": "клиническая полезность",
                        "implementation_feasibility": "осуществимость внедрения"
                    }}
                ],
                "early_warning_systems": [
                    {{
                        "system": "система раннего предупреждения",
                        "trigger_conditions": ["условие срабатывания 1", "условие срабатывания 2"],
                        "sensitivity": "чувствительность",
                        "specificity": "специфичность",
                        "alert_protocols": ["протокол предупреждения 1", "протокол предупреждения 2"]
                    }}
                ]
            }},
            "intervention_recommendations": {{
                "population_level_interventions": [
                    {{
                        "intervention": "популяционное вмешательство",
                        "target_population": "целевая популяция",
                        "implementation_strategy": "стратегия внедрения",
                        "expected_impact": "ожидаемое влияние",
                        "cost_effectiveness": "экономическая эффективность",
                        "feasibility_assessment": "оценка осуществимости",
                        "monitoring_indicators": ["индикатор мониторинга 1", "индикатор мониторинга 2"]
                    }}
                ],
                "targeted_interventions": [
                    {{
                        "intervention": "целевое вмешательство",
                        "high_risk_criteria": ["критерий высокого риска 1", "критерий высокого риска 2"],
                        "intervention_intensity": "интенсивность вмешательства",
                        "personalization_factors": ["фактор персонализации 1", "фактор персонализации 2"],
                        "delivery_mechanisms": ["механизм доставки 1", "механизм доставки 2"]
                    }}
                ],
                "policy_recommendations": [
                    {{
                        "policy_area": "область политики",
                        "recommended_changes": ["рекомендуемое изменение 1", "рекомендуемое изменение 2"],
                        "evidence_base": "доказательная база",
                        "stakeholder_engagement": "вовлечение заинтересованных сторон",
                        "implementation_barriers": ["барьер внедрения 1", "барьер внедрения 2"],
                        "success_factors": ["фактор успеха 1", "фактор успеха 2"]
                    }}
                ]
            }},
            "monitoring_framework": {{
                "surveillance_systems": [
                    {{
                        "system": "система наблюдения",
                        "data_sources": ["источник данных 1", "источник данных 2"],
                        "collection_frequency": "частота сбора",
                        "quality_indicators": ["индикатор качества 1", "индикатор качества 2"],
                        "reporting_mechanisms": ["механизм отчетности 1", "механизм отчетности 2"]
                    }}
                ],
                "performance_metrics": [
                    {{
                        "metric": "показатель производительности",
                        "measurement_method": "метод измерения",
                        "target_values": ["целевое значение 1", "целевое значение 2"],
                        "benchmarking": "бенчмаркинг",
                        "improvement_tracking": "отслеживание улучшений"
                    }}
                ]
            }},
            "research_priorities": [
                {{
                    "research_question": "исследовательский вопрос",
                    "knowledge_gap": "пробел в знаниях",
                    "research_design": "дизайн исследования",
                    "expected_outcomes": ["ожидаемый результат 1", "ожидаемый результат 2"],
                    "clinical_impact": "клиническое влияние",
                    "policy_implications": ["влияние на политику 1", "влияние на политику 2"]
                }}
            ]
        }}
        """
        
        system_prompt = """Вы эксперт по эпидемиологии и анализу рисков в здравоохранении с глубокими знаниями в области популяционной медицины, биостатистики и общественного здравоохранения.
        Анализируете популяционные данные для выявления паттернов рисков, факторов риска и разработки стратегий профилактики.
        Используете современные методы анализа данных и машинного обучения для выявления скрытых закономерностей в здоровье популяций.
        Предоставляете практические рекомендации по вмешательствам на популяционном уровне и политике здравоохранения.
        Ответы даете только в формате JSON."""
        
        request = AIRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4500
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
