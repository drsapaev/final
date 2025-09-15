"""
Mock AI провайдер для демонстрации и тестирования
"""
from typing import Dict, List, Optional, Any
import random
import asyncio
from .base_provider import BaseAIProvider, AIRequest, AIResponse
import logging

logger = logging.getLogger(__name__)


class MockProvider(BaseAIProvider):
    """Mock провайдер для демонстрации функционала без реального API"""
    
    def __init__(self, api_key: str = "mock", model: Optional[str] = None):
        super().__init__(api_key, model)
    
    def get_default_model(self) -> str:
        return "mock-model-v1"
    
    async def generate(self, request: AIRequest) -> AIResponse:
        """Имитация генерации ответа"""
        await asyncio.sleep(0.5)  # Имитация задержки API
        
        return AIResponse(
            content=f"Mock ответ на запрос: {request.prompt[:50]}...",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            model=self.model,
            provider=self.provider_name
        )
    
    async def analyze_complaint(self, complaint: str, patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Имитация анализа жалоб"""
        await asyncio.sleep(1)  # Имитация обработки
        
        # Генерируем правдоподобные результаты
        complaints_lower = complaint.lower()
        
        preliminary_diagnosis = []
        examinations = []
        lab_tests = []
        red_flags = []
        
        # Простая логика для демонстрации
        if "головн" in complaints_lower or "голов" in complaints_lower:
            preliminary_diagnosis.extend(["Мигрень", "Головная боль напряжения", "Гипертензия"])
            examinations.append({"type": "Инструментальное", "name": "МРТ головного мозга", "reason": "Исключение органической патологии"})
            lab_tests.extend(["Общий анализ крови", "Глюкоза крови"])
            
        if "тошнот" in complaints_lower:
            preliminary_diagnosis.append("Гастрит")
            lab_tests.append("Биохимический анализ крови")
            
        if "температур" in complaints_lower or "жар" in complaints_lower:
            preliminary_diagnosis.append("ОРВИ")
            lab_tests.append("СРБ")
            red_flags.append("Высокая температура более 3 дней")
            
        if "боль" in complaints_lower and "груд" in complaints_lower:
            preliminary_diagnosis.append("Стенокардия")
            examinations.append({"type": "Функциональное", "name": "ЭКГ", "reason": "Оценка сердечной деятельности"})
            red_flags.append("Боль в груди - требует немедленной оценки")
            
        # Если ничего не нашли, добавляем общие рекомендации
        if not preliminary_diagnosis:
            preliminary_diagnosis = ["Требуется дополнительное обследование"]
            
        if not lab_tests:
            lab_tests = ["Общий анализ крови", "Общий анализ мочи"]
            
        urgency = "экстренно" if red_flags else ("неотложно" if "сильн" in complaints_lower else "планово")
        
        return {
            "preliminary_diagnosis": preliminary_diagnosis,
            "examinations": examinations,
            "lab_tests": lab_tests,
            "consultations": ["Терапевт"] if not red_flags else ["Терапевт", "Кардиолог"],
            "urgency": urgency,
            "red_flags": red_flags
        }
    
    async def suggest_icd10(self, symptoms: List[str], diagnosis: Optional[str] = None) -> List[Dict[str, str]]:
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
            {"code": "E11", "name": "Сахарный диабет 2 типа"}
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
            elif any(word in icd["name"].lower() for s in symptoms_lower for word in s.split()):
                relevance = "средняя"
                
            if relevance != "низкая" or len(results) < 3:
                results.append({
                    "code": icd["code"],
                    "name": icd["name"],
                    "relevance": relevance
                })
                
        # Сортируем по релевантности
        relevance_order = {"высокая": 0, "средняя": 1, "низкая": 2}
        results.sort(key=lambda x: relevance_order[x["relevance"]])
        
        return results[:5]
    
    async def interpret_lab_results(self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
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
                        
                        abnormal_values.append({
                            "parameter": result["name"],
                            "value": result["value"],
                            "interpretation": f"{interpretation} (норма: {result['reference']})",
                            "clinical_significance": self._get_clinical_significance(result["name"], value > ref_max)
                        })
            except:
                pass
        
        # Генерируем возможные состояния на основе отклонений
        if any("Гемоглобин" in av["parameter"] for av in abnormal_values):
            possible_conditions.append("Анемия" if "Понижен" in str(abnormal_values) else "Полицитемия")
            recommendations.append("Консультация гематолога")
            
        if any("Лейкоциты" in av["parameter"] for av in abnormal_values):
            possible_conditions.append("Воспалительный процесс")
            recommendations.append("Поиск очага инфекции")
            
        urgency = "да" if len(abnormal_values) > 2 else "нет"
        
        return {
            "summary": f"Выявлено {len(abnormal_values)} отклонений от нормы" if abnormal_values else "Все показатели в пределах нормы",
            "abnormal_values": abnormal_values,
            "possible_conditions": possible_conditions,
            "recommendations": recommendations if recommendations else ["Контроль в динамике"],
            "urgency": urgency
        }
    
    def _get_clinical_significance(self, parameter: str, is_high: bool) -> str:
        """Получить клиническое значение отклонения"""
        significance_map = {
            "Гемоглобин": {
                True: "Возможна полицитемия, обезвоживание",
                False: "Возможна анемия, кровопотеря"
            },
            "Лейкоциты": {
                True: "Возможна инфекция, воспаление",
                False: "Возможна иммуносупрессия"
            },
            "СОЭ": {
                True: "Неспецифический маркер воспаления",
                False: "Обычно не имеет клинического значения"
            }
        }
        
        return significance_map.get(parameter, {}).get(is_high, "Требует клинической корреляции")
    
    async def analyze_skin(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Имитация анализа кожи"""
        await asyncio.sleep(1)
        
        # Случайная генерация для демонстрации
        skin_types = ["сухая", "жирная", "комбинированная", "нормальная"]
        problems = [
            ["акне", "расширенные поры"],
            ["сухость", "шелушение"],
            ["пигментация", "веснушки"],
            ["морщины", "потеря упругости"]
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
                "Регулярное очищение"
            ],
            "procedures": ["Чистка лица", "Увлажняющие маски"],
            "ai_confidence": "medium",
            "note": "Это демонстрационный анализ"
        }
    
    async def interpret_ecg(self, ecg_data: Dict[str, Any], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
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
            "interpretation": "ЭКГ в пределах нормы" if not abnormalities else f"Выявлены изменения: {', '.join(abnormalities)}",
            "recommendations": recommendations if recommendations else ["Контроль ЭКГ в динамике"],
            "urgency": urgency
        }
