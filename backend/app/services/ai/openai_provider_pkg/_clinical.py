"""Clinical mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    base64,
    json,
)


class ClinicalMixin(OpenAIProviderMixinBase):
    """Clinical methods for OpenAIProvider."""

    async def analyze_complaint(
        self, complaint: str, patient_info: dict | None = None
    ) -> dict[str, Any]:
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
            prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=1500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def suggest_icd10(
        self, symptoms: list[str], diagnosis: str | None = None
    ) -> list[dict[str, str]]:
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
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=800
        )

        response = await self.generate(request)

        if response.error:
            return []

        try:
            return json.loads(response.content)
        except Exception:
            return []


    async def interpret_lab_results(
        self, results: list[dict[str, Any]], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Интерпретация результатов анализов"""
        system_prompt = self._build_system_prompt("lab")

        results_text = "\n".join(
            [
                f"{r['name']}: {r['value']} {r.get('unit', '')} (норма: {r.get('reference', 'не указана')})"
                for r in results
            ]
        )

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
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=1500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def analyze_skin(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ кожи по фото через GPT-4 Vision"""
        try:
            # Кодируем изображение в base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            system_prompt = self._build_system_prompt("dermatologist")

            user_content = [
                {
                    "type": "text",
                    "text": "Проанализируйте состояние кожи на фото. Определите тип кожи, возможные проблемы и дайте рекомендации.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]

            if metadata:
                user_content[0][
                    "text"
                ] += f"\n\nДополнительная информация: {json.dumps(metadata, ensure_ascii=False)}"

            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1000,
                temperature=0.3,
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
                        "ai_confidence": "low",
                    }
            except Exception:
                return {"analysis": content, "structured": False}

        except Exception as e:
            return {"error": self._format_error(e)}


    async def interpret_ecg(
        self, ecg_data: dict[str, Any], patient_info: dict | None = None
    ) -> dict[str, Any]:
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
            prompt += (
                f"\nАвтоматическая интерпретация: {ecg_data['auto_interpretation']}"
            )

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
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=1200
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def differential_diagnosis(
        self, symptoms: list[str], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Дифференциальная диагностика на основе симптомов"""
        age = patient_info.get("age", "не указан") if patient_info else "не указан"
        gender = (
            patient_info.get("gender", "не указан") if patient_info else "не указан"
        )

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
            prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=1500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def symptom_analysis(
        self, symptoms: list[str], severity: list[int] | None = None
    ) -> dict[str, Any]:
        """Расширенный анализ симптомов с оценкой тяжести"""
        symptoms_with_severity = []

        for i, symptom in enumerate(symptoms):
            severity_score = severity[i] if severity and i < len(severity) else None
            if severity_score:
                symptoms_with_severity.append(
                    f"{symptom} (тяжесть: {severity_score}/10)"
                )
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
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=1200
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def clinical_decision_support(
        self, case_data: dict[str, Any]
    ) -> dict[str, Any]:
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
            prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=2000
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }

    # Новые методы для анализа медицинских изображений


