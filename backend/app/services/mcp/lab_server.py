"""
MCP сервер для лабораторных анализов
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from .base_server import BaseMCPServer, MCPTool, MCPResource
from ..ai.ai_manager import get_ai_manager, AIProviderType

logger = logging.getLogger(__name__)


class MedicalLabMCPServer(BaseMCPServer):
    """MCP сервер для работы с лабораторными анализами"""
    
    def __init__(self):
        super().__init__(name="medical-lab-server", version="1.0.0")
        self.ai_manager = None
        self.normal_ranges = self._load_normal_ranges()
        self.test_panels = self._load_test_panels()
    
    async def initialize(self):
        """Инициализация сервера"""
        self.ai_manager = get_ai_manager()
        logger.info("Medical Lab MCP Server initialized")
    
    async def shutdown(self):
        """Завершение работы сервера"""
        logger.info("Medical Lab MCP Server shutting down")
    
    def _load_normal_ranges(self) -> Dict[str, Dict[str, Any]]:
        """Загрузка нормальных диапазонов для анализов"""
        return {
            "hemoglobin": {
                "name": "Гемоглобин",
                "unit": "г/л",
                "male": {"min": 130, "max": 170},
                "female": {"min": 120, "max": 150},
                "critical_low": 70,
                "critical_high": 200
            },
            "glucose": {
                "name": "Глюкоза",
                "unit": "ммоль/л",
                "normal": {"min": 3.3, "max": 5.5},
                "fasting": {"min": 3.3, "max": 5.5},
                "postprandial": {"min": 4.0, "max": 7.8},
                "critical_low": 2.2,
                "critical_high": 25.0
            },
            "cholesterol": {
                "name": "Холестерин общий",
                "unit": "ммоль/л",
                "optimal": {"max": 5.2},
                "borderline": {"min": 5.2, "max": 6.2},
                "high": {"min": 6.2},
                "critical_high": 10.0
            },
            "creatinine": {
                "name": "Креатинин",
                "unit": "мкмоль/л",
                "male": {"min": 62, "max": 106},
                "female": {"min": 44, "max": 88},
                "critical_high": 500
            },
            "alt": {
                "name": "АЛТ",
                "unit": "Ед/л",
                "male": {"max": 41},
                "female": {"max": 33},
                "critical_high": 500
            },
            "ast": {
                "name": "АСТ",
                "unit": "Ед/л",
                "male": {"max": 40},
                "female": {"max": 32},
                "critical_high": 500
            },
            "tsh": {
                "name": "ТТГ",
                "unit": "мЕд/л",
                "normal": {"min": 0.4, "max": 4.0},
                "pregnancy_1st": {"min": 0.1, "max": 2.5},
                "critical_low": 0.01,
                "critical_high": 100
            }
        }
    
    def _load_test_panels(self) -> Dict[str, Dict[str, Any]]:
        """Загрузка панелей анализов"""
        return {
            "general_blood": {
                "name": "Общий анализ крови",
                "tests": ["hemoglobin", "erythrocytes", "leukocytes", "platelets", "esr"],
                "indications": ["Скрининг", "Анемия", "Инфекции", "Воспаление"]
            },
            "biochemistry_basic": {
                "name": "Биохимия базовая",
                "tests": ["glucose", "cholesterol", "alt", "ast", "creatinine", "urea"],
                "indications": ["Скрининг", "Заболевания печени", "Заболевания почек"]
            },
            "lipid_profile": {
                "name": "Липидный профиль",
                "tests": ["cholesterol", "ldl", "hdl", "triglycerides"],
                "indications": ["Атеросклероз", "ИБС", "Дислипидемия"]
            },
            "thyroid_panel": {
                "name": "Щитовидная железа",
                "tests": ["tsh", "t3_free", "t4_free", "anti_tpo"],
                "indications": ["Гипотиреоз", "Гипертиреоз", "Зоб"]
            },
            "diabetes_panel": {
                "name": "Диабетическая панель",
                "tests": ["glucose", "hba1c", "insulin", "c_peptide"],
                "indications": ["Диабет", "Преддиабет", "Метаболический синдром"]
            },
            "liver_panel": {
                "name": "Печеночная панель",
                "tests": ["alt", "ast", "ggt", "alkaline_phosphatase", "bilirubin_total", "bilirubin_direct"],
                "indications": ["Гепатит", "Цирроз", "Желтуха"]
            },
            "kidney_panel": {
                "name": "Почечная панель",
                "tests": ["creatinine", "urea", "uric_acid", "potassium", "sodium", "egfr"],
                "indications": ["ХБП", "Острая почечная недостаточность", "Нефрит"]
            }
        }
    
    @MCPTool(name="interpret_lab_results", description="Интерпретация результатов лабораторных анализов")
    async def interpret_lab_results(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """
        Интерпретация лабораторных результатов
        
        Args:
            results: Список результатов анализов
            patient_info: Информация о пациенте
            provider: AI провайдер
            include_recommendations: Включить рекомендации
        
        Returns:
            Интерпретация результатов
        """
        try:
            # Анализируем отклонения
            abnormal_results = self._analyze_abnormalities(results, patient_info)
            
            # Определяем провайдер
            provider_type = None
            if provider:
                try:
                    provider_type = AIProviderType(provider.lower())
                except ValueError:
                    logger.warning(f"Invalid provider: {provider}, using default")
            
            # Получаем AI интерпретацию
            ai_interpretation = await self.ai_manager.interpret_lab_results(
                results=results,
                patient_info=patient_info,
                provider_type=provider_type
            )
            
            # Формируем полный ответ
            response = {
                "status": "success",
                "summary": {
                    "total_tests": len(results),
                    "abnormal_count": len(abnormal_results),
                    "critical_count": sum(1 for r in abnormal_results if r.get("is_critical")),
                    "overall_assessment": self._get_overall_assessment(abnormal_results)
                },
                "abnormal_results": abnormal_results,
                "ai_interpretation": ai_interpretation,
                "metadata": {
                    "provider_used": provider or "default",
                    "timestamp": datetime.utcnow().isoformat(),
                    "patient_age": patient_info.get("age") if patient_info else None,
                    "patient_gender": patient_info.get("gender") if patient_info else None
                }
            }
            
            if include_recommendations:
                response["recommendations"] = self._generate_recommendations(abnormal_results, ai_interpretation)
            
            return response
            
        except Exception as e:
            logger.error(f"Error interpreting lab results: {str(e)}")
            return {
                "status": "error",
                "error": f"Failed to interpret results: {str(e)}"
            }
    
    @MCPTool(name="check_critical_values", description="Проверка критических значений в анализах")
    async def check_critical_values(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Проверка критических значений
        
        Args:
            results: Результаты анализов
        
        Returns:
            Список критических значений
        """
        critical_values = []
        
        for result in results:
            test_name = result.get("test_name", "").lower()
            value = result.get("value")
            
            if not value:
                continue
            
            # Проверяем в справочнике нормальных диапазонов
            if test_name in self.normal_ranges:
                ranges = self.normal_ranges[test_name]
                
                # Проверка критически низких значений
                if "critical_low" in ranges and value < ranges["critical_low"]:
                    critical_values.append({
                        "test": result.get("test_name"),
                        "value": value,
                        "unit": result.get("unit", ranges.get("unit")),
                        "type": "critical_low",
                        "threshold": ranges["critical_low"],
                        "action": "Требуется немедленное медицинское вмешательство"
                    })
                
                # Проверка критически высоких значений
                if "critical_high" in ranges and value > ranges["critical_high"]:
                    critical_values.append({
                        "test": result.get("test_name"),
                        "value": value,
                        "unit": result.get("unit", ranges.get("unit")),
                        "type": "critical_high",
                        "threshold": ranges["critical_high"],
                        "action": "Требуется немедленное медицинское вмешательство"
                    })
        
        return {
            "has_critical": len(critical_values) > 0,
            "critical_count": len(critical_values),
            "critical_values": critical_values,
            "urgency": "emergency" if critical_values else "routine"
        }
    
    @MCPTool(name="suggest_follow_up_tests", description="Рекомендации дополнительных анализов")
    async def suggest_follow_up_tests(
        self,
        current_results: List[Dict[str, Any]],
        abnormal_findings: List[str],
        clinical_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Рекомендации дополнительных анализов
        
        Args:
            current_results: Текущие результаты
            abnormal_findings: Отклонения
            clinical_context: Клинический контекст
        
        Returns:
            Рекомендации по дополнительным анализам
        """
        suggestions = []
        
        # Анализируем текущие результаты
        current_tests = {r.get("test_name", "").lower() for r in current_results}
        
        # Правила для дополнительных анализов
        follow_up_rules = {
            "glucose": {
                "if_high": ["hba1c", "insulin", "c_peptide"],
                "if_low": ["insulin", "cortisol", "growth_hormone"]
            },
            "alt": {
                "if_high": ["ast", "ggt", "alkaline_phosphatase", "hepatitis_markers"],
                "if_low": []
            },
            "tsh": {
                "if_high": ["t3_free", "t4_free", "anti_tpo", "anti_tg"],
                "if_low": ["t3_free", "t4_free", "cortisol"]
            },
            "creatinine": {
                "if_high": ["urea", "potassium", "egfr", "urine_protein"],
                "if_low": []
            }
        }
        
        # Проверяем аномальные результаты
        for result in current_results:
            test_name = result.get("test_name", "").lower()
            if test_name in follow_up_rules:
                value = result.get("value")
                normal_range = self.normal_ranges.get(test_name)
                
                if normal_range and value:
                    # Определяем отклонение
                    is_high = False
                    is_low = False
                    
                    if "normal" in normal_range:
                        is_high = value > normal_range["normal"].get("max", float('inf'))
                        is_low = value < normal_range["normal"].get("min", 0)
                    
                    # Добавляем рекомендации
                    if is_high and follow_up_rules[test_name]["if_high"]:
                        for test in follow_up_rules[test_name]["if_high"]:
                            if test not in current_tests:
                                suggestions.append({
                                    "test": test,
                                    "reason": f"Повышен {test_name}",
                                    "priority": "high"
                                })
                    
                    if is_low and follow_up_rules[test_name]["if_low"]:
                        for test in follow_up_rules[test_name]["if_low"]:
                            if test not in current_tests:
                                suggestions.append({
                                    "test": test,
                                    "reason": f"Понижен {test_name}",
                                    "priority": "medium"
                                })
        
        # Удаляем дубликаты
        unique_suggestions = []
        seen_tests = set()
        for sugg in suggestions:
            if sugg["test"] not in seen_tests:
                unique_suggestions.append(sugg)
                seen_tests.add(sugg["test"])
        
        return {
            "suggestions": unique_suggestions,
            "total_count": len(unique_suggestions),
            "clinical_context": clinical_context
        }
    
    @MCPResource(name="normal_ranges", description="Нормальные диапазоны для анализов")
    async def get_normal_ranges(
        self,
        test_name: Optional[str] = None,
        patient_gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение нормальных диапазонов
        
        Args:
            test_name: Название теста
            patient_gender: Пол пациента
        
        Returns:
            Нормальные диапазоны
        """
        if test_name:
            test_key = test_name.lower()
            if test_key in self.normal_ranges:
                ranges = self.normal_ranges[test_key].copy()
                
                # Выбираем диапазон по полу если есть
                if patient_gender and patient_gender.lower() in ["male", "female"]:
                    gender_key = patient_gender.lower()
                    if gender_key in ranges:
                        ranges["applicable_range"] = ranges[gender_key]
                
                return {
                    "test": test_name,
                    "ranges": ranges,
                    "gender_specific": "male" in ranges or "female" in ranges
                }
            else:
                return {
                    "error": f"Test {test_name} not found in reference ranges"
                }
        
        # Возвращаем все диапазоны
        return {
            "ranges": self.normal_ranges,
            "total_count": len(self.normal_ranges),
            "tests": list(self.normal_ranges.keys())
        }
    
    @MCPResource(name="test_panels", description="Панели лабораторных анализов")
    async def get_test_panels(
        self,
        panel_name: Optional[str] = None,
        indication: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение панелей анализов
        
        Args:
            panel_name: Название панели
            indication: Показание для анализов
        
        Returns:
            Информация о панелях
        """
        if panel_name:
            panel = self.test_panels.get(panel_name)
            if panel:
                return {
                    "panel": panel_name,
                    "details": panel
                }
            else:
                return {
                    "error": f"Panel {panel_name} not found"
                }
        
        # Фильтр по показанию
        if indication:
            relevant_panels = []
            for name, panel in self.test_panels.items():
                if any(indication.lower() in ind.lower() for ind in panel.get("indications", [])):
                    relevant_panels.append({
                        "name": name,
                        "details": panel
                    })
            
            return {
                "indication": indication,
                "panels": relevant_panels,
                "count": len(relevant_panels)
            }
        
        # Все панели
        return {
            "panels": self.test_panels,
            "total_count": len(self.test_panels),
            "names": list(self.test_panels.keys())
        }
    
    def _analyze_abnormalities(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Анализ отклонений в результатах"""
        abnormal = []
        
        for result in results:
            test_name = result.get("test_name", "").lower()
            value = result.get("value")
            
            if not value or test_name not in self.normal_ranges:
                continue
            
            ranges = self.normal_ranges[test_name]
            is_abnormal = False
            deviation_type = None
            is_critical = False
            
            # Определяем применимый диапазон
            if patient_info and patient_info.get("gender"):
                gender = patient_info["gender"].lower()
                if gender in ranges:
                    normal_range = ranges[gender]
                elif "normal" in ranges:
                    normal_range = ranges["normal"]
                else:
                    continue
            elif "normal" in ranges:
                normal_range = ranges["normal"]
            else:
                continue
            
            # Проверка отклонений
            if "min" in normal_range and value < normal_range["min"]:
                is_abnormal = True
                deviation_type = "low"
                if "critical_low" in ranges and value < ranges["critical_low"]:
                    is_critical = True
            
            if "max" in normal_range and value > normal_range["max"]:
                is_abnormal = True
                deviation_type = "high"
                if "critical_high" in ranges and value > ranges["critical_high"]:
                    is_critical = True
            
            if is_abnormal:
                abnormal.append({
                    "test": result.get("test_name"),
                    "value": value,
                    "unit": result.get("unit", ranges.get("unit")),
                    "normal_range": normal_range,
                    "deviation": deviation_type,
                    "is_critical": is_critical,
                    "interpretation": self._get_interpretation(test_name, deviation_type, is_critical)
                })
        
        return abnormal
    
    def _get_interpretation(self, test_name: str, deviation: str, is_critical: bool) -> str:
        """Получение интерпретации отклонения"""
        interpretations = {
            "glucose": {
                "high": "Возможен диабет или преддиабет" if not is_critical else "Гипергликемический криз",
                "low": "Гипогликемия" if not is_critical else "Критическая гипогликемия"
            },
            "hemoglobin": {
                "high": "Возможна полицитемия или обезвоживание",
                "low": "Анемия" if not is_critical else "Тяжелая анемия"
            },
            "alt": {
                "high": "Возможно повреждение печени" if not is_critical else "Острое повреждение печени",
                "low": "Обычно не имеет клинического значения"
            }
        }
        
        if test_name in interpretations and deviation in interpretations[test_name]:
            return interpretations[test_name][deviation]
        
        return f"{'Критическое' if is_critical else 'Умеренное'} отклонение {'выше' if deviation == 'high' else 'ниже'} нормы"
    
    def _get_overall_assessment(self, abnormal_results: List[Dict[str, Any]]) -> str:
        """Общая оценка результатов"""
        if not abnormal_results:
            return "Все показатели в пределах нормы"
        
        critical_count = sum(1 for r in abnormal_results if r.get("is_critical"))
        
        if critical_count > 0:
            return f"Требуется срочная медицинская консультация - {critical_count} критических отклонений"
        elif len(abnormal_results) > 5:
            return "Множественные отклонения - рекомендуется консультация врача"
        elif len(abnormal_results) > 2:
            return "Несколько отклонений - рекомендуется консультация врача"
        else:
            return "Незначительные отклонения - рекомендуется наблюдение"
    
    def _generate_recommendations(
        self,
        abnormal_results: List[Dict[str, Any]],
        ai_interpretation: Dict[str, Any]
    ) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        # Базовые рекомендации по критическим значениям
        critical_tests = [r for r in abnormal_results if r.get("is_critical")]
        if critical_tests:
            recommendations.append("⚠️ Немедленно обратитесь к врачу - обнаружены критические отклонения")
        
        # Рекомендации по типам отклонений
        high_glucose = any(r["test"].lower() == "glucose" and r["deviation"] == "high" for r in abnormal_results)
        if high_glucose:
            recommendations.append("📊 Контроль уровня глюкозы, возможна консультация эндокринолога")
        
        low_hemoglobin = any(r["test"].lower() == "hemoglobin" and r["deviation"] == "low" for r in abnormal_results)
        if low_hemoglobin:
            recommendations.append("🩸 Дообследование для выявления причин анемии")
        
        # Добавляем рекомендации из AI если есть
        if ai_interpretation and not ai_interpretation.get("error"):
            # Здесь можно добавить парсинг AI рекомендаций
            pass
        
        return recommendations if recommendations else ["✅ Продолжайте наблюдение у лечащего врача"]
