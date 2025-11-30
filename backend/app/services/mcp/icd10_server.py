"""
MCP сервер для работы с МКБ-10
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..ai.ai_manager import AIProviderType, get_ai_manager
from .base_server import BaseMCPServer, MCPResource, MCPTool

logger = logging.getLogger(__name__)


class MedicalICD10MCPServer(BaseMCPServer):
    """MCP сервер для работы с кодами МКБ-10"""

    def __init__(self):
        super().__init__(name="medical-icd10-server", version="1.0.0")
        self.ai_manager = None
        self.icd10_cache = {}
        self.common_codes = self._load_common_codes()

    async def initialize(self):
        """Инициализация сервера"""
        self.ai_manager = get_ai_manager()
        logger.info("Medical ICD-10 MCP Server initialized")

    async def shutdown(self):
        """Завершение работы сервера"""
        logger.info("Medical ICD-10 MCP Server shutting down")

    def _load_common_codes(self) -> Dict[str, Dict[str, str]]:
        """Загрузка часто используемых кодов МКБ-10"""
        return {
            "respiratory": {
                "J06.9": "Острая инфекция верхних дыхательных путей неуточненная",
                "J00": "Острый назофарингит (насморк)",
                "J02.9": "Острый фарингит неуточненный",
                "J03.9": "Острый тонзиллит неуточненный (ангина)",
                "J04.0": "Острый ларингит",
                "J20.9": "Острый бронхит неуточненный",
                "J18.9": "Пневмония неуточненная",
                "J18.0": "Бронхопневмония неуточненная",
                "J45.9": "Астма неуточненная",
                "J45.0": "Астма с преобладанием аллергического компонента",
                "J44.0": "ХОБЛ с острой респираторной инфекцией",
                "J44.9": "ХОБЛ неуточненная",
                "J32.9": "Хронический синусит неуточненный",
                "J31.0": "Хронический ринит",
                "U07.1": "COVID-19 вирус идентифицирован",
                "U09.9": "Состояние после COVID-19 неуточненное (длительный ковид)",
            },
            "cardiovascular": {
                "I10": "Эссенциальная (первичная) гипертензия",
                "I11.9": "Гипертензивная болезнь сердца без сердечной недостаточности",
                "I20.0": "Нестабильная стенокардия",
                "I20.9": "Стенокардия неуточненная",
                "I21.9": "Острый инфаркт миокарда неуточненный",
                "I25.1": "Атеросклеротическая болезнь сердца",
                "I48.0": "Фибрилляция предсердий пароксизмальная",
                "I48.1": "Фибрилляция предсердий постоянная",
                "I49.9": "Нарушение сердечного ритма неуточненное",
                "I50.0": "Застойная сердечная недостаточность",
                "I50.9": "Сердечная недостаточность неуточненная",
                "I63.9": "Инфаркт мозга неуточненный",
                "I64": "Инсульт неуточненный",
                "I67.9": "Цереброваскулярная болезнь неуточненная",
                "I73.9": "Болезнь периферических сосудов неуточненная",
                "I80.3": "Флебит и тромбофлебит нижних конечностей",
            },
            "gastrointestinal": {
                "K29.7": "Гастрит неуточненный",
                "K25.9": "Язва желудка неуточненная",
                "K58.9": "Синдром раздраженного кишечника",
                "K92.1": "Мелена",
                "K80.2": "Желчнокаменная болезнь",
            },
            "neurological": {
                "G43.9": "Мигрень неуточненная",
                "G43.0": "Мигрень без ауры",
                "G43.1": "Мигрень с аурой",
                "G44.2": "Головная боль напряжения",
                "G44.0": "Синдром кластерной головной боли",
                "G40.9": "Эпилепсия неуточненная",
                "G40.3": "Генерализованная идиопатическая эпилепсия",
                "G20": "Болезнь Паркинсона",
                "G35": "Рассеянный склероз",
                "G45.9": "Транзиторная церебральная ишемическая атака неуточненная",
                "G47.0": "Нарушения засыпания и поддержания сна (бессонница)",
                "G50.0": "Невралгия тройничного нерва",
                "G51.0": "Паралич Белла",
                "G56.0": "Синдром запястного канала",
                "G62.9": "Полиневропатия неуточненная",
                "R51": "Головная боль",
                "R55": "Обморок и коллапс",
            },
            "endocrine": {
                "E11.9": "Сахарный диабет 2 типа без осложнений",
                "E10.9": "Сахарный диабет 1 типа без осложнений",
                "E03.9": "Гипотиреоз неуточненный",
                "E05.9": "Тиреотоксикоз неуточненный",
                "E66.9": "Ожирение неуточненное",
            },
            "dermatological": {
                "L20.9": "Атопический дерматит неуточненный",
                "L40.9": "Псориаз неуточненный",
                "L50.9": "Крапивница неуточненная",
                "L70.0": "Угри обыкновенные",
                "B07": "Вирусные бородавки",
            },
            "dental": {
                "K02.9": "Кариес зубов неуточненный",
                "K04.0": "Пульпит",
                "K04.5": "Хронический апикальный периодонтит",
                "K05.0": "Острый гингивит",
                "K05.1": "Хронический гингивит",
                "K08.1": "Потеря зубов вследствие несчастного случая",
                "K12.0": "Рецидивирующие афты полости рта",
                "K12.1": "Другие формы стоматита",
            },
            "symptoms": {
                "R00.0": "Тахикардия неуточненная",
                "R00.1": "Брадикардия неуточненная",
                "R00.2": "Сердцебиение",
                "R03.0": "Повышенное артериальное давление",
                "R04.0": "Носовое кровотечение",
                "R04.2": "Кровохарканье",
                "R05": "Кашель",
                "R06.0": "Одышка",
                "R06.2": "Свистящее дыхание",
                "R07.0": "Боль в горле",
                "R07.2": "Боль в области сердца",
                "R07.3": "Другая боль в груди",
                "R07.4": "Боль в грудной клетке неуточненная",
                "R10.0": "Острый живот",
                "R10.1": "Боль в верхней части живота",
                "R10.3": "Боль в нижней части живота",
                "R10.4": "Другие и неуточненные боли в животе",
                "R11": "Тошнота и рвота",
                "R11.0": "Тошнота",
                "R11.1": "Рвота",
                "R12": "Изжога",
                "R13.1": "Дисфагия (нарушение глотания)",
                "R14": "Метеоризм и родственные состояния",
                "R19.4": "Изменение функции кишечника",
                "R19.5": "Другие нарушения стула",
                "R19.6": "Неприятный запах стула",
                "R19.7": "Диарея неуточненная",
                "R20.0": "Анестезия кожи",
                "R20.2": "Парестезия кожи",
                "R21": "Сыпь и другие неспецифические изменения кожи",
                "R22.9": "Локализованная припухлость, образование и уплотнение кожи",
                "R25.1": "Тремор неуточненный",
                "R25.2": "Судорога и спазм",
                "R26.2": "Затруднения при ходьбе",
                "R29.6": "Склонность к падениям",
                "R42": "Головокружение и нарушение устойчивости",
                "R50.9": "Лихорадка неуточненная",
                "R51": "Головная боль",
                "R52.0": "Острая боль",
                "R52.1": "Хроническая неустранимая боль",
                "R52.9": "Боль неуточненная",
                "R53": "Недомогание и утомляемость",
                "R55": "Обморок и коллапс",
                "R56.0": "Судороги при лихорадке",
                "R56.8": "Другие и неуточненные судороги",
                "R60.0": "Локализованный отек",
                "R60.9": "Отек неуточненный",
                "R61": "Гипергидроз (повышенная потливость)",
                "R63.0": "Анорексия (потеря аппетита)",
                "R63.3": "Затруднения при кормлении",
                "R63.4": "Аномальная потеря массы тела",
                "R63.5": "Аномальное увеличение массы тела",
                "R68.0": "Гипотермия, не связанная с низкой температурой окружающей среды",
                "R68.1": "Неспецифические симптомы, свойственные младенчеству",
                "R68.2": "Сухость во рту неуточненная",
                "R68.3": "Симптом в виде «барабанных палочек» (пальцев)",
                "R68.8": "Другие уточненные общие симптомы и признаки",
                "R73.0": "Нарушение толерантности к глюкозе",
                "R73.9": "Гипергликемия неуточненная",
            },
            "infections": {
                "A09.9": "Гастроэнтерит и колит неуточненного происхождения",
                "B34.9": "Вирусная инфекция неуточненная",
                "N39.0": "Инфекция мочевыводящих путей",
                "L03.9": "Флегмона неуточненная",
                "H66.9": "Средний отит неуточненный",
            },
        }

    @MCPTool(
        name="suggest_icd10", description="Подсказки кодов МКБ-10 на основе симптомов"
    )
    async def suggest_icd10(
        self,
        symptoms: List[str],
        diagnosis: Optional[str] = None,
        specialty: Optional[str] = None,
        provider: Optional[str] = None,
        max_suggestions: int = 5,
    ) -> Dict[str, Any]:
        """
        Подсказки кодов МКБ-10

        Args:
            symptoms: Список симптомов
            diagnosis: Предварительный диагноз
            specialty: Специальность врача
            provider: AI провайдер
            max_suggestions: Максимум подсказок

        Returns:
            Список рекомендованных кодов МКБ-10
        """
        try:
            # Определяем провайдер
            provider_type = None
            if provider:
                try:
                    provider_type = AIProviderType(provider.lower())
                except ValueError:
                    logger.warning(f"Invalid provider: {provider}, using default")

            # Получаем подсказки через AI
            suggestions = await self.ai_manager.suggest_icd10(
                symptoms=symptoms, diagnosis=diagnosis, provider_type=provider_type
            )

            # Проверяем, получили ли мы детальные клинические рекомендации
            if (
                suggestions
                and len(suggestions) > 0
                and "clinical_recommendations" in suggestions[0]
            ):
                # Новый формат: детальные клинические рекомендации
                return {
                    "status": "success",
                    "clinical_recommendations": suggestions[0][
                        "clinical_recommendations"
                    ],
                    "metadata": {
                        "symptoms_count": len(symptoms),
                        "has_diagnosis": diagnosis is not None,
                        "specialty": specialty,
                        "provider_used": provider or "default",
                        "timestamp": datetime.utcnow().isoformat(),
                        "format": "detailed_clinical",
                    },
                }
            else:
                # Старый формат: список кодов
                # Добавляем релевантные коды из кеша
                relevant_codes = self._find_relevant_cached_codes(
                    symptoms, diagnosis, specialty
                )

                # Объединяем результаты
                all_suggestions = suggestions[:max_suggestions]

                # Добавляем кешированные коды если есть место
                for code in relevant_codes:
                    if len(all_suggestions) < max_suggestions:
                        if not any(
                            s.get("code") == code["code"] for s in all_suggestions
                        ):
                            all_suggestions.append(code)

                return {
                    "status": "success",
                    "suggestions": all_suggestions,
                    "metadata": {
                        "symptoms_count": len(symptoms),
                        "has_diagnosis": diagnosis is not None,
                        "specialty": specialty,
                        "provider_used": provider or "default",
                        "timestamp": datetime.utcnow().isoformat(),
                        "format": "code_list",
                    },
                }

        except Exception as e:
            logger.error(f"Error suggesting ICD-10 codes: {str(e)}")
            return {
                "status": "error",
                "error": f"Failed to suggest ICD-10 codes: {str(e)}",
                "suggestions": [],
            }

    @MCPTool(name="validate_icd10", description="Валидация кода МКБ-10")
    async def validate_icd10(
        self,
        code: str,
        symptoms: Optional[List[str]] = None,
        diagnosis: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Валидация кода МКБ-10

        Args:
            code: Код МКБ-10
            symptoms: Список симптомов для проверки соответствия
            diagnosis: Диагноз для проверки соответствия

        Returns:
            Результат валидации
        """
        # Базовая валидация формата
        import re

        pattern = r'^[A-Z]\d{2}(\.\d{1,2})?$'

        if not re.match(pattern, code.upper()):
            return {
                "valid": False,
                "reason": "Неверный формат кода МКБ-10",
                "format_hint": "Формат: буква + 2 цифры + опционально точка и 1-2 цифры (например, I10 или I10.0)",
            }

        # Проверяем в кеше
        code_info = self._find_code_in_cache(code.upper())

        relevance_score = 1.0
        warnings = []

        # Проверка соответствия симптомам
        if symptoms and code_info:
            # Упрощенная проверка релевантности
            description_lower = code_info.get("description", "").lower()
            matching_symptoms = sum(
                1
                for s in symptoms
                if any(word in description_lower for word in s.lower().split())
            )
            relevance_score = matching_symptoms / len(symptoms) if symptoms else 1.0

            if relevance_score < 0.3:
                warnings.append("Код может не соответствовать указанным симптомам")

        return {
            "valid": True,
            "code": code.upper(),
            "description": code_info.get("description") if code_info else None,
            "category": code_info.get("category") if code_info else None,
            "relevance_score": round(relevance_score, 2),
            "warnings": warnings,
        }

    @MCPTool(name="search_icd10", description="Поиск кодов МКБ-10 по тексту")
    async def search_icd10(
        self, query: str, category: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Поиск кодов МКБ-10

        Args:
            query: Поисковый запрос
            category: Категория для фильтрации
            limit: Максимум результатов

        Returns:
            Найденные коды МКБ-10
        """
        results = []
        query_lower = query.lower()
        query_upper = query.upper()

        # Поиск в кешированных кодах
        for cat, codes in self.common_codes.items():
            if category and cat != category:
                continue

            for code, description in codes.items():
                description_lower = description.lower()

                # Проверяем совпадение по коду (точное или частичное)
                code_match = False
                code_score = 0.0
                if query_upper in code:
                    code_match = True
                    code_score = 1.0 if query_upper == code else 0.95

                # Проверяем совпадение по описанию
                text_match = query_lower in description_lower
                text_score = self._calculate_match_score(query_lower, description_lower)

                # Если есть хоть какое-то совпадение - добавляем
                if code_match or text_match or text_score > 0.3:
                    # Приоритет: совпадение по коду > совпадение по описанию
                    final_score = max(code_score, text_score)
                    results.append(
                        {
                            "code": code,
                            "description": description,
                            "category": cat,
                            "match_score": final_score,
                            "match_type": "code" if code_match else "description",
                        }
                    )

        # Сортируем по релевантности (код важнее описания)
        results.sort(
            key=lambda x: (x["match_score"], x["match_type"] == "code"), reverse=True
        )

        return {
            "status": "success",
            "results": results[:limit],
            "total_found": len(results),
            "query": query,
            "category_filter": category,
        }

    @MCPResource(
        name="common_icd10_codes", description="Часто используемые коды МКБ-10"
    )
    async def get_common_codes(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение часто используемых кодов

        Args:
            category: Фильтр по категории

        Returns:
            Список часто используемых кодов
        """
        if category:
            codes = self.common_codes.get(category, {})
            return {
                "category": category,
                "codes": [{"code": k, "description": v} for k, v in codes.items()],
                "count": len(codes),
            }

        all_codes = []
        for cat, codes in self.common_codes.items():
            for code, description in codes.items():
                all_codes.append(
                    {"code": code, "description": description, "category": cat}
                )

        return {
            "codes": all_codes,
            "total_count": len(all_codes),
            "categories": list(self.common_codes.keys()),
        }

    @MCPResource(name="icd10_categories", description="Категории МКБ-10")
    async def get_categories(self) -> Dict[str, Any]:
        """Получение списка категорий МКБ-10"""
        categories = {
            "A00-B99": "Инфекционные и паразитарные болезни",
            "C00-D48": "Новообразования",
            "D50-D89": "Болезни крови и кроветворных органов",
            "E00-E90": "Болезни эндокринной системы",
            "F00-F99": "Психические расстройства",
            "G00-G99": "Болезни нервной системы",
            "H00-H59": "Болезни глаза",
            "H60-H95": "Болезни уха",
            "I00-I99": "Болезни системы кровообращения",
            "J00-J99": "Болезни органов дыхания",
            "K00-K93": "Болезни органов пищеварения",
            "L00-L99": "Болезни кожи",
            "M00-M99": "Болезни костно-мышечной системы",
            "N00-N99": "Болезни мочеполовой системы",
            "O00-O99": "Беременность, роды",
            "P00-P96": "Перинатальный период",
            "Q00-Q99": "Врожденные аномалии",
            "R00-R99": "Симптомы и признаки",
            "S00-T98": "Травмы и отравления",
            "V01-Y98": "Внешние причины",
            "Z00-Z99": "Факторы, влияющие на здоровье",
        }

        return {
            "categories": [
                {"range": k, "description": v} for k, v in categories.items()
            ],
            "total_count": len(categories),
        }

    def _find_relevant_cached_codes(
        self, symptoms: List[str], diagnosis: Optional[str], specialty: Optional[str]
    ) -> List[Dict[str, str]]:
        """Поиск релевантных кодов в кеше"""
        relevant = []

        # Определяем категорию по специальности
        specialty_mapping = {
            "cardiology": "cardiovascular",
            "pulmonology": "respiratory",
            "gastroenterology": "gastrointestinal",
            "neurology": "neurological",
            "endocrinology": "endocrine",
            "dermatology": "dermatological",
            "dentistry": "dental",
        }

        category = specialty_mapping.get(specialty) if specialty else None

        # Ищем в соответствующей категории или во всех
        search_categories = [category] if category else list(self.common_codes.keys())

        for cat in search_categories:
            codes = self.common_codes.get(cat, {})
            for code, description in codes.items():
                score = self._calculate_relevance(description, symptoms, diagnosis)
                if score > 0.3:
                    relevant.append(
                        {
                            "code": code,
                            "description": description,
                            "category": cat,
                            "relevance_score": score,
                        }
                    )

        # Сортируем по релевантности
        relevant.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant[:3]

    def _find_code_in_cache(self, code: str) -> Optional[Dict[str, str]]:
        """Поиск кода в кеше"""
        for category, codes in self.common_codes.items():
            if code in codes:
                return {"code": code, "description": codes[code], "category": category}
        return None

    def _calculate_relevance(
        self, description: str, symptoms: List[str], diagnosis: Optional[str]
    ) -> float:
        """Расчет релевантности кода"""
        score = 0.0
        description_lower = description.lower()

        # Проверка симптомов
        if symptoms:
            for symptom in symptoms:
                words = symptom.lower().split()
                matching = sum(1 for word in words if word in description_lower)
                score += matching / len(words) if words else 0
            score = score / len(symptoms) if symptoms else 0

        # Проверка диагноза
        if diagnosis:
            diagnosis_words = diagnosis.lower().split()
            matching = sum(1 for word in diagnosis_words if word in description_lower)
            diagnosis_score = matching / len(diagnosis_words) if diagnosis_words else 0
            score = (score + diagnosis_score * 2) / 3  # Диагноз важнее

        return min(score, 1.0)

    def _calculate_match_score(self, query: str, text: str) -> float:
        """Расчет точности совпадения с поддержкой нечеткого поиска"""
        if query == text:
            return 1.0

        # Если весь запрос содержится в тексте - высокий балл
        if query in text:
            return 0.9

        # Если текст содержится в запросе - средний балл
        if text in query:
            return 0.7

        words = query.split()
        if not words:
            return 0.0

        # Подсчет полных совпадений слов
        full_matches = sum(1 for word in words if word in text)

        # Подсчет частичных совпадений (начало слова)
        partial_matches = 0
        text_words = text.split()
        for query_word in words:
            if len(query_word) >= 3:  # Минимум 3 символа для частичного поиска
                for text_word in text_words:
                    if text_word.startswith(query_word) or query_word.startswith(
                        text_word
                    ):
                        partial_matches += 0.5
                        break

        # Финальный балл: полные совпадения важнее частичных
        total_score = (full_matches + partial_matches) / len(words)
        return min(total_score, 1.0)
