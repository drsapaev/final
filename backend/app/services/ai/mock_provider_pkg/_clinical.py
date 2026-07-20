"""Clinical mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    Any,
    MockProviderMixinBase,
    asyncio,
    random,
)


class ClinicalMixin(MockProviderMixinBase):
    """Clinical methods for MockProvider."""

    async def analyze_complaint(
        self, complaint: str, patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Имитация анализа жалоб с детальными результатами"""
        await asyncio.sleep(1)  # Имитация обработки

        # Генерируем правдоподобные результаты
        complaints_lower = complaint.lower()

        preliminary_diagnosis = []
        examinations = []
        lab_tests = []
        red_flags = []
        consultations = []

        # Детальная логика для различных симптомов
        if "головн" in complaints_lower or "голов" in complaints_lower:
            preliminary_diagnosis.extend(
                [
                    "Мигрень с аурой или без ауры",
                    "Головная боль напряженного типа",
                    "Артериальная гипертензия",
                    "Цервикогенная головная боль",
                ]
            )
            examinations.extend(
                [
                    {
                        "type": "Инструментальное",
                        "name": "МРТ головного мозга с контрастированием",
                        "reason": "Исключение органической патологии (опухоли, сосудистые мальформации)",
                    },
                    {
                        "type": "Инструментальное",
                        "name": "УЗДГ сосудов головы и шеи",
                        "reason": "Оценка церебрального кровотока и выявление стенозов",
                    },
                    {
                        "type": "Функциональное",
                        "name": "ЭЭГ",
                        "reason": "Исключение эпилептической активности",
                    },
                ]
            )
            lab_tests.extend(
                [
                    "Общий анализ крови с лейкоформулой",
                    "Биохимический анализ крови (глюкоза, липидограмма)",
                    "Коагулограмма",
                    "Гормоны щитовидной железы (ТТГ, Т3, Т4)",
                ]
            )
            consultations.extend(
                ["Невролог", "Офтальмолог (для исключения внутричерепной гипертензии)"]
            )

        if "тошнот" in complaints_lower or "рвот" in complaints_lower:
            if "головн" in complaints_lower:
                preliminary_diagnosis.append("Вестибулопатия")
                preliminary_diagnosis.append("Менингит (при наличии других симптомов)")
                consultations.append("Оториноларинголог")
            else:
                preliminary_diagnosis.extend(
                    [
                        "Гастрит острый или хронический",
                        "Гастроэзофагеальная рефлюксная болезнь (ГЭРБ)",
                        "Пищевое отравление",
                        "Язвенная болезнь желудка",
                    ]
                )
                examinations.append(
                    {
                        "type": "Инструментальное",
                        "name": "ФГДС (фиброгастродуоденоскопия)",
                        "reason": "Визуализация слизистой оболочки желудка и двенадцатиперстной кишки",
                    }
                )
                consultations.append("Гастроэнтеролог")
            lab_tests.append(
                "Биохимический анализ крови (АЛТ, АСТ, билирубин, амилаза)"
            )

        if (
            "температур" in complaints_lower
            or "жар" in complaints_lower
            or "лихорад" in complaints_lower
        ):
            preliminary_diagnosis.extend(
                [
                    "ОРВИ (грипп, COVID-19, др.)",
                    "Бактериальная инфекция (требует уточнения локализации)",
                    "Воспалительный процесс неясной этиологии",
                ]
            )
            lab_tests.extend(
                [
                    "Общий анализ крови с лейкоформулой",
                    "СРБ (С-реактивный белок)",
                    "Прокальцитонин (при подозрении на бактериальную инфекцию)",
                    "Посев крови на стерильность (при высокой лихорадке)",
                ]
            )
            red_flags.append(
                "⚠️ Лихорадка >38.5°C более 3 дней или >39°C требует обязательной консультации врача"
            )
            red_flags.append(
                "⚠️ Сопутствующие симптомы: ригидность затылочных мышц, спутанность сознания, петехиальная сыпь"
            )
            consultations.extend(
                [
                    "Терапевт",
                    "Инфекционист (при подозрении на инфекционное заболевание)",
                ]
            )

        if "боль" in complaints_lower and "груд" in complaints_lower:
            preliminary_diagnosis.extend(
                [
                    "⚠️ Острый коронарный синдром (ОКС) - требует немедленной оценки!",
                    "Стенокардия напряжения",
                    "Межреберная невралгия",
                    "ГЭРБ (рефлюксная болезнь)",
                    "Плеврит",
                    "Пневмония",
                ]
            )
            examinations.extend(
                [
                    {
                        "type": "ЭКСТРЕННОЕ",
                        "name": "ЭКГ в 12 отведениях",
                        "reason": "⚠️ ЭКСТРЕННО! Исключение острого инфаркта миокарда и других острых состояний",
                    },
                    {
                        "type": "Лабораторное",
                        "name": "Тропонины I/T",
                        "reason": "⚠️ ЭКСТРЕННО! Маркеры повреждения миокарда",
                    },
                    {
                        "type": "Инструментальное",
                        "name": "Рентгенография органов грудной клетки",
                        "reason": "Исключение пневмонии, плеврита, пневмоторакса",
                    },
                    {
                        "type": "Инструментальное",
                        "name": "ЭхоКГ (УЗИ сердца)",
                        "reason": "Оценка сократимости миокарда, состояния клапанов",
                    },
                ]
            )
            lab_tests.extend(
                [
                    "⚠️ Тропонины I/T (экстренно!)",
                    "Креатинкиназа-МВ (КФК-МВ)",
                    "Общий анализ крови",
                    "Д-димер (при подозрении на ТЭЛА)",
                ]
            )
            red_flags.extend(
                [
                    "🚨 ЭКСТРЕННО! Боль в груди давящего/сжимающего характера",
                    "🚨 Иррадиация боли в левую руку, челюсть, шею",
                    "🚨 Одышка, холодный пот, тошнота",
                    "🚨 Требуется НЕМЕДЛЕННАЯ консультация врача или вызов скорой помощи!",
                ]
            )
            consultations.extend(
                ["🚨 ЭКСТРЕННАЯ госпитализация", "Кардиолог", "Пульмонолог"]
            )

        if "кашел" in complaints_lower or "одышк" in complaints_lower:
            preliminary_diagnosis.extend(
                [
                    "ОРВИ",
                    "Бронхит острый",
                    "Пневмония",
                    "Бронхиальная астма (обострение)",
                    "ХОБЛ (обострение)",
                ]
            )
            examinations.extend(
                [
                    {
                        "type": "Инструментальное",
                        "name": "Рентгенография органов грудной клетки",
                        "reason": "Исключение пневмонии, туберкулеза",
                    },
                    {
                        "type": "Функциональное",
                        "name": "Спирометрия",
                        "reason": "Оценка функции внешнего дыхания",
                    },
                ]
            )
            lab_tests.extend(
                ["Общий анализ крови", "СРБ", "Посев мокроты (при продуктивном кашле)"]
            )
            consultations.append("Пульмонолог")

        if (
            "кож" in complaints_lower
            or "сып" in complaints_lower
            or "зуд" in complaints_lower
        ):
            preliminary_diagnosis.extend(
                [
                    "Аллергический дерматит",
                    "Крапивница",
                    "Атопический дерматит",
                    "Инфекционная экзантема",
                ]
            )
            examinations.append(
                {
                    "type": "Специализированное",
                    "name": "Дерматоскопия",
                    "reason": "Детальная оценка кожных элементов",
                }
            )
            lab_tests.extend(["Общий анализ крови", "IgE общий и специфический"])
            consultations.append("Дерматолог")

        # Если ничего не нашли, добавляем общие рекомендации
        if not preliminary_diagnosis:
            preliminary_diagnosis = [
                "Требуется дополнительное обследование для уточнения диагноза",
                "Рекомендована консультация терапевта для сбора анамнеза и осмотра",
            ]

        if not lab_tests:
            lab_tests = [
                "Общий анализ крови с лейкоформулой",
                "Общий анализ мочи",
                "Биохимический анализ крови (базовая панель)",
            ]

        if not consultations:
            consultations = ["Терапевт"]

        urgency = (
            "экстренно"
            if red_flags and "🚨" in str(red_flags)
            else (
                "неотложно" if (red_flags or "сильн" in complaints_lower) else "планово"
            )
        )

        return {
            "preliminary_diagnosis": preliminary_diagnosis,
            "examinations": examinations,
            "lab_tests": lab_tests,
            "consultations": consultations,
            "urgency": urgency,
            "red_flags": red_flags,
        }


    async def suggest_icd10(
        self, symptoms: list[str], diagnosis: str | None = None
    ) -> list[dict[str, str]]:
        """Имитация подсказок МКБ-10"""
        await asyncio.sleep(0.5)

        # Примеры кодов МКБ-10
        icd_database = [
            {"code": "G43", "name": "Мигрень"},
            {"code": "G44.2", "name": "Головная боль напряженного типа"},
            {"code": "R51", "name": "Головная боль"},
            {"code": "I10", "name": "Эссенциальная (первичная) гипертензия"},
            {"code": "K29", "name": "Гастрит и дуоденит"},
            {"code": "J06", "name": "Острые инфекции верхних дыхательных путей"},
            {"code": "I20", "name": "Стенокардия"},
            {"code": "R11", "name": "Тошнота и рвота"},
            {"code": "R50", "name": "Лихорадка неясного происхождения"},
            {"code": "E11", "name": "Сахарный диабет 2 типа"},
        ]

        results = []
        symptoms_lower = [s.lower() for s in symptoms]

        for icd in icd_database:
            relevance = "низкая"

            # Проверяем соответствие симптомам
            if any("голов" in s for s in symptoms_lower) and "G4" in icd["code"]:
                relevance = "высокая"
            elif diagnosis and diagnosis.lower() in icd["name"].lower():
                relevance = "высокая"
            elif any(
                word in icd["name"].lower()
                for s in symptoms_lower
                for word in s.split()
            ):
                relevance = "средняя"

            if relevance != "низкая" or len(results) < 3:
                results.append(
                    {"code": icd["code"], "name": icd["name"], "relevance": relevance}
                )

        # Сортируем по релевантности
        relevance_order = {"высокая": 0, "средняя": 1, "низкая": 2}
        results.sort(key=lambda x: relevance_order[x["relevance"]])

        return results[:5]


    async def interpret_lab_results(
        self, results: list[dict[str, Any]], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Имитация интерпретации анализов"""
        await asyncio.sleep(1)

        abnormal_values = []
        possible_conditions = []
        recommendations = []

        for result in results:
            try:
                value = float(result["value"])
                ref_range = result.get("reference", "").split("-")

                if len(ref_range) == 2:
                    ref_min = float(ref_range[0])
                    ref_max = float(ref_range[1])

                    if value < ref_min or value > ref_max:
                        interpretation = "Повышен" if value > ref_max else "Понижен"

                        abnormal_values.append(
                            {
                                "parameter": result["name"],
                                "value": result["value"],
                                "interpretation": f"{interpretation} (норма: {result['reference']})",
                                "clinical_significance": self._get_clinical_significance(
                                    result["name"], value > ref_max
                                ),
                            }
                        )
            except Exception:
                pass

        # Генерируем возможные состояния на основе отклонений
        if any("Гемоглобин" in av["parameter"] for av in abnormal_values):
            possible_conditions.append(
                "Анемия" if "Понижен" in str(abnormal_values) else "Полицитемия"
            )
            recommendations.append("Консультация гематолога")

        if any("Лейкоциты" in av["parameter"] for av in abnormal_values):
            possible_conditions.append("Воспалительный процесс")
            recommendations.append("Поиск очага инфекции")

        urgency = "да" if len(abnormal_values) > 2 else "нет"

        return {
            "summary": (
                f"Выявлено {len(abnormal_values)} отклонений от нормы"
                if abnormal_values
                else "Все показатели в пределах нормы"
            ),
            "abnormal_values": abnormal_values,
            "possible_conditions": possible_conditions,
            "recommendations": (
                recommendations if recommendations else ["Контроль в динамике"]
            ),
            "urgency": urgency,
        }


    async def analyze_skin(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Имитация анализа кожи"""
        await asyncio.sleep(1)

        # Случайная генерация для демонстрации
        skin_types = ["сухая", "жирная", "комбинированная", "нормальная"]
        problems = [
            ["акне", "расширенные поры"],
            ["сухость", "шелушение"],
            ["пигментация", "веснушки"],
            ["морщины", "потеря упругости"],
        ]

        selected_type = random.choice(skin_types)
        selected_problems = random.choice(problems)

        return {
            "skin_type": selected_type,
            "problems": selected_problems,
            "skin_condition": "хорошее",
            "recommendations": [
                f"Использовать увлажняющие средства для {selected_type} кожи",
                "SPF защита ежедневно",
                "Регулярное очищение",
            ],
            "procedures": ["Чистка лица", "Увлажняющие маски"],
            "ai_confidence": "medium",
            "note": "Это демонстрационный анализ",
        }


    async def interpret_ecg(
        self, ecg_data: dict[str, Any], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Имитация интерпретации ЭКГ"""
        await asyncio.sleep(0.8)

        params = ecg_data.get('parameters', {})
        hr = params.get('heart_rate', 75)

        abnormalities = []
        recommendations = []

        # Простая логика для демонстрации
        if hr > 100:
            abnormalities.append("Тахикардия")
            recommendations.append("Исключить тиреотоксикоз")
        elif hr < 60:
            abnormalities.append("Брадикардия")
            recommendations.append("Холтер-мониторирование")

        if params.get('qt_interval', 0) > 440:
            abnormalities.append("Удлинение интервала QT")
            recommendations.append("Контроль электролитов")

        urgency = "планово"
        if len(abnormalities) > 1:
            urgency = "неотложно"

        return {
            "rhythm": "Синусовый ритм" if 60 <= hr <= 100 else "Нарушение ритма",
            "rate": f"{hr} уд/мин",
            "conduction": "Нормальная",
            "axis": "Нормальное положение",
            "abnormalities": abnormalities if abnormalities else ["Без особенностей"],
            "interpretation": (
                "ЭКГ в пределах нормы"
                if not abnormalities
                else f"Выявлены изменения: {', '.join(abnormalities)}"
            ),
            "recommendations": (
                recommendations if recommendations else ["Контроль ЭКГ в динамике"]
            ),
            "urgency": urgency,
        }


    async def differential_diagnosis(
        self, symptoms: list[str], patient_info: dict | None = None
    ) -> dict[str, Any]:
        """Имитация дифференциальной диагностики"""
        await asyncio.sleep(1.5)

        # Простая логика для демонстрации
        mock_diagnoses = [
            {
                "diagnosis": "ОРВИ",
                "probability": 75,
                "icd10_code": "J06.9",
                "reasoning": "Соответствие симптомов вирусной инфекции",
            },
            {
                "diagnosis": "Бактериальная инфекция",
                "probability": 20,
                "icd10_code": "J20.9",
                "reasoning": "Возможное бактериальное осложнение",
            },
            {
                "diagnosis": "Аллергическая реакция",
                "probability": 5,
                "icd10_code": "T78.4",
                "reasoning": "Менее вероятно при данных симптомах",
            },
        ]

        return {
            "differential_diagnoses": mock_diagnoses,
            "clarifying_questions": [
                "Есть ли повышение температуры?",
                "Как долго длятся симптомы?",
                "Были ли контакты с больными?",
            ],
            "recommended_tests": [
                "Общий анализ крови",
                "С-реактивный белок",
                "Мазок из зева",
            ],
            "red_flags": [
                "Температура выше 39°C",
                "Затрудненное дыхание",
                "Боль в груди",
            ],
            "urgency_level": "средний",
        }


    async def symptom_analysis(
        self, symptoms: list[str], severity: list[int] | None = None
    ) -> dict[str, Any]:
        """Имитация анализа симптомов"""
        await asyncio.sleep(1)

        # Группировка симптомов по системам
        symptom_groups = {
            "cardiovascular": [],
            "respiratory": [],
            "neurological": [],
            "gastrointestinal": [],
            "other": [],
        }

        for symptom in symptoms:
            if any(
                word in symptom.lower()
                for word in ["сердце", "боль в груди", "сердцебиение"]
            ):
                symptom_groups["cardiovascular"].append(symptom)
            elif any(
                word in symptom.lower() for word in ["кашель", "одышка", "дыхание"]
            ):
                symptom_groups["respiratory"].append(symptom)
            elif any(
                word in symptom.lower()
                for word in ["головная боль", "головокружение", "слабость"]
            ):
                symptom_groups["neurological"].append(symptom)
            elif any(
                word in symptom.lower()
                for word in ["тошнота", "рвота", "боль в животе"]
            ):
                symptom_groups["gastrointestinal"].append(symptom)
            else:
                symptom_groups["other"].append(symptom)

        # Удаляем пустые группы
        symptom_groups = {k: v for k, v in symptom_groups.items() if v}

        overall_score = random.randint(3, 8)

        return {
            "symptom_groups": symptom_groups,
            "symptom_relationships": [
                {
                    "symptoms": symptoms[:2] if len(symptoms) >= 2 else symptoms,
                    "relationship": "Возможная связь через общий патогенез",
                }
            ],
            "severity_assessment": {
                "overall_score": overall_score,
                "description": (
                    "умеренное состояние"
                    if overall_score < 6
                    else "состояние средней тяжести"
                ),
                "most_concerning": [symptoms[0]] if symptoms else [],
            },
            "possible_syndromes": ["Астенический синдром", "Интоксикационный синдром"],
            "examination_priority": [
                "Общий анализ крови",
                "Биохимический анализ крови",
            ],
        }


    async def clinical_decision_support(
        self, case_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация поддержки клинических решений"""
        await asyncio.sleep(2)

        return {
            "data_analysis": "Представленные данные указывают на острое состояние с умеренной степенью тяжести",
            "primary_diagnosis": {
                "diagnosis": "Острая респираторная инфекция",
                "confidence": 80,
                "icd10_code": "J06.9",
            },
            "investigation_plan": [
                {
                    "test": "Общий анализ крови",
                    "priority": "высокий",
                    "rationale": "Оценка воспалительной реакции",
                },
                {
                    "test": "Рентген грудной клетки",
                    "priority": "средний",
                    "rationale": "Исключение пневмонии",
                },
            ],
            "treatment_recommendations": [
                {
                    "intervention": "Симптоматическая терапия",
                    "details": "Жаропонижающие при температуре выше 38.5°C",
                    "monitoring": "Температура тела, общее состояние",
                }
            ],
            "prognosis": {
                "short_term": "Благоприятный при адекватном лечении",
                "long_term": "Полное выздоровление ожидается в течение 7-10 дней",
            },
            "referral_criteria": [
                "Ухудшение состояния в течение 48 часов",
                "Появление одышки или боли в груди",
            ],
        }


