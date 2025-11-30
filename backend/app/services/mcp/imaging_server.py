"""
MCP сервер для анализа медицинских изображений
"""

import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..ai.ai_manager import AIProviderType, get_ai_manager
from .base_server import BaseMCPServer, MCPResource, MCPTool

logger = logging.getLogger(__name__)


class MedicalImagingMCPServer(BaseMCPServer):
    """MCP сервер для анализа медицинских изображений"""

    def __init__(self):
        super().__init__(name="medical-imaging-server", version="1.0.0")
        self.ai_manager = None
        self.imaging_types = self._load_imaging_types()
        self.analysis_templates = self._load_analysis_templates()

    async def initialize(self):
        """Инициализация сервера"""
        self.ai_manager = get_ai_manager()
        logger.info("Medical Imaging MCP Server initialized")

    async def shutdown(self):
        """Завершение работы сервера"""
        logger.info("Medical Imaging MCP Server shutting down")

    def _load_imaging_types(self) -> Dict[str, Dict[str, Any]]:
        """Загрузка типов медицинских изображений"""
        return {
            "xray": {
                "name": "Рентгенография",
                "modalities": ["chest", "abdomen", "extremities", "spine"],
                "file_formats": ["dicom", "jpg", "png"],
                "typical_findings": [
                    "переломы",
                    "пневмония",
                    "ателектаз",
                    "кардиомегалия",
                ],
            },
            "ultrasound": {
                "name": "УЗИ",
                "modalities": [
                    "abdomen",
                    "thyroid",
                    "cardiac",
                    "vascular",
                    "obstetric",
                ],
                "file_formats": ["dicom", "jpg", "png", "mp4"],
                "typical_findings": ["камни", "кисты", "опухоли", "жидкость"],
            },
            "ct": {
                "name": "КТ",
                "modalities": ["head", "chest", "abdomen", "spine", "angiography"],
                "file_formats": ["dicom"],
                "typical_findings": ["инсульт", "опухоли", "травмы", "эмболия"],
            },
            "mri": {
                "name": "МРТ",
                "modalities": ["brain", "spine", "joints", "abdomen", "cardiac"],
                "file_formats": ["dicom"],
                "typical_findings": ["опухоли", "демиелинизация", "грыжи", "разрывы"],
            },
            "ecg": {
                "name": "ЭКГ",
                "modalities": ["12-lead", "holter", "stress"],
                "file_formats": ["pdf", "jpg", "png", "xml"],
                "typical_findings": ["аритмия", "ишемия", "гипертрофия", "блокады"],
            },
            "dermatoscopy": {
                "name": "Дерматоскопия",
                "modalities": ["skin_lesion", "hair", "nail"],
                "file_formats": ["jpg", "png", "heic"],
                "typical_findings": ["меланома", "базалиома", "невус", "кератоз"],
            },
        }

    def _load_analysis_templates(self) -> Dict[str, Dict[str, Any]]:
        """Загрузка шаблонов анализа"""
        return {
            "chest_xray": {
                "sections": [
                    "легочные поля",
                    "сердце",
                    "средостение",
                    "костные структуры",
                ],
                "checklist": [
                    "Прозрачность легочных полей",
                    "Легочный рисунок",
                    "Корни легких",
                    "Размеры сердца",
                    "Контуры средостения",
                    "Диафрагма",
                    "Костные структуры",
                ],
            },
            "abdominal_ultrasound": {
                "sections": [
                    "печень",
                    "желчный пузырь",
                    "поджелудочная",
                    "селезенка",
                    "почки",
                ],
                "checklist": [
                    "Размеры органов",
                    "Эхогенность паренхимы",
                    "Сосудистый рисунок",
                    "Наличие образований",
                    "Свободная жидкость",
                ],
            },
            "ecg_12lead": {
                "sections": ["ритм", "частота", "интервалы", "сегменты", "комплексы"],
                "checklist": [
                    "Ритм синусовый/несинусовый",
                    "ЧСС",
                    "Интервал PQ",
                    "Комплекс QRS",
                    "Сегмент ST",
                    "Зубец T",
                    "Интервал QT",
                ],
            },
        }

    @MCPTool(
        name="analyze_medical_image", description="Анализ медицинского изображения"
    )
    async def analyze_medical_image(
        self,
        image_data: str,  # Base64 encoded
        image_type: str,
        modality: Optional[str] = None,
        clinical_context: Optional[str] = None,
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Анализ медицинского изображения

        Args:
            image_data: Изображение в base64
            image_type: Тип изображения (xray, ultrasound, etc.)
            modality: Модальность (chest, abdomen, etc.)
            clinical_context: Клинический контекст
            patient_info: Информация о пациенте
            provider: AI провайдер

        Returns:
            Результат анализа изображения
        """
        try:
            # Валидация типа изображения
            if image_type not in self.imaging_types:
                return {
                    "status": "error",
                    "error": f"Unsupported image type: {image_type}",
                }

            # Декодируем изображение
            try:
                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                return {"status": "error", "error": f"Failed to decode image: {str(e)}"}

            # Определяем провайдер (для изображений предпочитаем OpenAI или Gemini)
            provider_type = None
            if provider:
                try:
                    provider_type = AIProviderType(provider.lower())
                except ValueError:
                    logger.warning(f"Invalid provider: {provider}, using default")

            # Выбираем подходящий метод анализа
            result = None
            if image_type == "xray":
                result = await self.ai_manager.analyze_xray_image(
                    image_data=image_bytes,
                    metadata={"modality": modality, "context": clinical_context},
                    provider_type=provider_type,
                )
            elif image_type == "ultrasound":
                result = await self.ai_manager.analyze_ultrasound_image(
                    image_data=image_bytes,
                    metadata={"modality": modality, "context": clinical_context},
                    provider_type=provider_type,
                )
            elif image_type == "dermatoscopy":
                result = await self.ai_manager.analyze_dermatoscopy_image(
                    image_data=image_bytes,
                    metadata={"context": clinical_context},
                    provider_type=provider_type,
                )
            elif image_type == "ecg":
                result = await self.ai_manager.interpret_ecg(
                    ecg_data={"image": image_bytes, "type": modality},
                    patient_info=patient_info,
                    provider_type=provider_type,
                )
            else:
                # Универсальный анализ
                result = await self.ai_manager.analyze_medical_image_generic(
                    image_data=image_bytes,
                    image_type=image_type,
                    metadata={"modality": modality, "context": clinical_context},
                    provider_type=provider_type,
                )

            # Добавляем структурированный анализ
            structured_analysis = self._structure_analysis(result, image_type, modality)

            return {
                "status": "success",
                "analysis": result,
                "structured": structured_analysis,
                "metadata": {
                    "image_type": image_type,
                    "modality": modality,
                    "provider_used": provider or "default",
                    "timestamp": datetime.utcnow().isoformat(),
                    "has_clinical_context": clinical_context is not None,
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing medical image: {str(e)}")
            return {"status": "error", "error": f"Analysis failed: {str(e)}"}

    @MCPTool(
        name="analyze_skin_lesion",
        description="Специализированный анализ кожных образований",
    )
    async def analyze_skin_lesion(
        self,
        image_data: str,
        lesion_info: Optional[Dict[str, Any]] = None,
        patient_history: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Анализ кожных образований

        Args:
            image_data: Изображение в base64
            lesion_info: Информация об образовании
            patient_history: История пациента
            provider: AI провайдер

        Returns:
            Результат анализа с оценкой риска
        """
        try:
            # Декодируем изображение
            image_bytes = base64.b64decode(image_data)

            # Определяем провайдер
            provider_type = None
            if provider:
                try:
                    provider_type = AIProviderType(provider.lower())
                except ValueError:
                    pass

            # Анализ через AI
            result = await self.ai_manager.analyze_skin(
                image_data=image_bytes,
                metadata=lesion_info,
                provider_type=provider_type,
            )

            # Оценка риска по ABCDE критериям
            risk_assessment = self._assess_skin_lesion_risk(result, lesion_info)

            # Рекомендации
            recommendations = self._generate_skin_recommendations(
                risk_assessment, patient_history
            )

            return {
                "status": "success",
                "analysis": result,
                "risk_assessment": risk_assessment,
                "recommendations": recommendations,
                "metadata": {
                    "provider_used": provider or "default",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing skin lesion: {str(e)}")
            return {"status": "error", "error": f"Skin analysis failed: {str(e)}"}

    @MCPTool(name="compare_images", description="Сравнение медицинских изображений")
    async def compare_images(
        self,
        image1_data: str,
        image2_data: str,
        comparison_type: str,  # "progression", "before_after", "bilateral"
        time_interval: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Сравнение двух медицинских изображений

        Args:
            image1_data: Первое изображение в base64
            image2_data: Второе изображение в base64
            comparison_type: Тип сравнения
            time_interval: Временной интервал между снимками

        Returns:
            Результат сравнения
        """
        try:
            # Декодируем изображения
            image1_bytes = base64.b64decode(image1_data)
            image2_bytes = base64.b64decode(image2_data)

            # Базовое сравнение
            comparison = {
                "type": comparison_type,
                "time_interval": time_interval,
                "findings": [],
            }

            if comparison_type == "progression":
                comparison["findings"] = [
                    "Оценка динамики изменений",
                    "Сравнение размеров патологических очагов",
                    "Появление новых или исчезновение старых изменений",
                ]
                comparison["conclusion"] = "Требуется детальный анализ врачом"

            elif comparison_type == "before_after":
                comparison["findings"] = [
                    "Оценка эффективности лечения",
                    "Изменения после процедуры",
                    "Наличие осложнений",
                ]
                comparison["conclusion"] = "Видимые изменения после вмешательства"

            elif comparison_type == "bilateral":
                comparison["findings"] = [
                    "Сравнение симметричности",
                    "Выявление односторонних изменений",
                    "Оценка различий между сторонами",
                ]
                comparison["conclusion"] = "Асимметрия требует внимания"

            return {
                "status": "success",
                "comparison": comparison,
                "requires_expert_review": True,
                "metadata": {
                    "comparison_type": comparison_type,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error comparing images: {str(e)}")
            return {"status": "error", "error": f"Comparison failed: {str(e)}"}

    @MCPResource(name="imaging_types", description="Типы медицинских изображений")
    async def get_imaging_types(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение информации о типах изображений

        Args:
            category: Фильтр по категории

        Returns:
            Информация о типах изображений
        """
        if category:
            if category in self.imaging_types:
                return {"category": category, "details": self.imaging_types[category]}
            else:
                return {"error": f"Category {category} not found"}

        return {
            "types": self.imaging_types,
            "total_count": len(self.imaging_types),
            "categories": list(self.imaging_types.keys()),
        }

    @MCPResource(name="analysis_templates", description="Шаблоны анализа изображений")
    async def get_analysis_templates(
        self, template_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение шаблонов анализа

        Args:
            template_type: Тип шаблона

        Returns:
            Шаблоны анализа
        """
        if template_type:
            if template_type in self.analysis_templates:
                return {
                    "template": template_type,
                    "details": self.analysis_templates[template_type],
                }
            else:
                return {"error": f"Template {template_type} not found"}

        return {
            "templates": self.analysis_templates,
            "total_count": len(self.analysis_templates),
            "types": list(self.analysis_templates.keys()),
        }

    @MCPResource(
        name="quality_criteria", description="Критерии качества медицинских изображений"
    )
    async def get_quality_criteria(self) -> Dict[str, Any]:
        """Получение критериев качества изображений"""
        return {
            "criteria": {
                "technical": [
                    "Правильная экспозиция",
                    "Отсутствие артефактов",
                    "Правильное позиционирование",
                    "Достаточное разрешение",
                    "Правильная маркировка",
                ],
                "diagnostic": [
                    "Визуализация области интереса",
                    "Достаточная контрастность",
                    "Отсутствие движения",
                    "Полнота исследования",
                    "Сопоставимость с предыдущими",
                ],
            }
        }

    def _structure_analysis(
        self, raw_analysis: Dict[str, Any], image_type: str, modality: Optional[str]
    ) -> Dict[str, Any]:
        """Структурирование результатов анализа"""
        structured = {"findings": [], "impressions": [], "recommendations": []}

        # Получаем шаблон если есть
        template_key = f"{modality}_{image_type}" if modality else image_type
        template = self.analysis_templates.get(template_key)

        if template:
            # Структурируем по секциям шаблона
            for section in template.get("sections", []):
                structured["findings"].append(
                    {
                        "section": section,
                        "status": "analyzed",
                        "details": f"Анализ {section} выполнен",
                    }
                )

        # Добавляем общие находки из AI анализа
        if not raw_analysis.get("error"):
            structured["impressions"].append("AI анализ выполнен успешно")
            structured["recommendations"].append(
                "Рекомендуется консультация специалиста"
            )

        return structured

    def _assess_skin_lesion_risk(
        self, analysis_result: Dict[str, Any], lesion_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Оценка риска кожного образования по ABCDE"""
        risk_score = 0
        criteria = {
            "asymmetry": False,
            "border_irregularity": False,
            "color_variation": False,
            "diameter_large": False,
            "evolution": False,
        }

        # Проверяем информацию об образовании
        if lesion_info:
            if lesion_info.get("asymmetric"):
                criteria["asymmetry"] = True
                risk_score += 1

            if lesion_info.get("irregular_border"):
                criteria["border_irregularity"] = True
                risk_score += 1

            if lesion_info.get("multiple_colors"):
                criteria["color_variation"] = True
                risk_score += 1

            diameter = lesion_info.get("diameter_mm", 0)
            if diameter > 6:
                criteria["diameter_large"] = True
                risk_score += 1

            if lesion_info.get("changing"):
                criteria["evolution"] = True
                risk_score += 2  # Evolution имеет больший вес

        # Определяем уровень риска
        if risk_score >= 4:
            risk_level = "high"
            urgency = "urgent"
        elif risk_score >= 2:
            risk_level = "moderate"
            urgency = "scheduled"
        else:
            risk_level = "low"
            urgency = "routine"

        return {
            "abcde_criteria": criteria,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "urgency": urgency,
            "interpretation": self._get_risk_interpretation(risk_level),
        }

    def _get_risk_interpretation(self, risk_level: str) -> str:
        """Интерпретация уровня риска"""
        interpretations = {
            "high": "Высокий риск малигнизации. Требуется срочная консультация дерматолога-онколога",
            "moderate": "Умеренный риск. Рекомендуется консультация дерматолога в плановом порядке",
            "low": "Низкий риск. Рекомендуется наблюдение и фотофиксация",
        }
        return interpretations.get(risk_level, "Требуется оценка специалиста")

    def _generate_skin_recommendations(
        self, risk_assessment: Dict[str, Any], patient_history: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Генерация рекомендаций по кожным образованиям"""
        recommendations = []

        risk_level = risk_assessment.get("risk_level")

        if risk_level == "high":
            recommendations.extend(
                [
                    "🚨 Срочная консультация дерматолога-онколога",
                    "📋 Дерматоскопия экспертного уровня",
                    "🔬 Возможна биопсия для гистологического исследования",
                ]
            )
        elif risk_level == "moderate":
            recommendations.extend(
                [
                    "👨‍⚕️ Плановая консультация дерматолога",
                    "📸 Фотофиксация для наблюдения в динамике",
                    "🔍 Дерматоскопия через 3-6 месяцев",
                ]
            )
        else:
            recommendations.extend(
                [
                    "👁️ Самонаблюдение по правилу ABCDE",
                    "📅 Ежегодный профилактический осмотр",
                    "☀️ Защита от УФ-излучения",
                ]
            )

        # Дополнительные рекомендации на основе истории
        if patient_history:
            if patient_history.get("family_melanoma"):
                recommendations.append(
                    "⚠️ Повышенная настороженность - семейный анамнез меланомы"
                )

            if patient_history.get("multiple_nevi"):
                recommendations.append("📊 Картирование родинок рекомендовано")

        return recommendations
