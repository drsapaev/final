"""Imaging mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    Any,
    MockProviderMixinBase,
    asyncio,
)


class ImagingMixin(MockProviderMixinBase):
    """Imaging methods for MockProvider."""

    async def analyze_xray_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Имитация анализа рентгеновского снимка"""
        await asyncio.sleep(2)

        body_part = (
            metadata.get("body_part", "грудная клетка")
            if metadata
            else "грудная клетка"
        )

        return {
            "technical_quality": {
                "positioning": "правильное",
                "exposure": "оптимальная",
                "artifacts": [],
            },
            "anatomical_structures": {
                "bones": ["Костные структуры без видимых изменений"],
                "soft_tissues": ["Мягкие ткани в норме"],
                "organs": ["Легочные поля без патологии"],
            },
            "pathological_findings": [],
            "normal_findings": [
                "Костно-суставная система без патологии",
                "Легочные поля чистые",
                "Сердечная тень в норме",
            ],
            "recommendations": {
                "additional_studies": [],
                "follow_up": "Контрольное исследование через 6 месяцев",
                "urgent_consultation": "не требуется",
            },
            "conclusion": f"Рентгенография {body_part}: патологии не выявлено",
            "confidence_level": "высокая",
        }


    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Имитация анализа УЗИ изображения"""
        await asyncio.sleep(1.5)

        organ = metadata.get("organ", "печень") if metadata else "печень"

        return {
            "image_quality": {
                "resolution": "хорошая",
                "depth_penetration": "достаточная",
                "artifacts": [],
            },
            "anatomical_assessment": {
                "organ_visualization": "хорошая",
                "size_measurements": {
                    "length": "не измерено",
                    "width": "не измерено",
                    "thickness": "не измерено",
                },
                "echogenicity": "нормальная",
                "structure": "однородная",
            },
            "pathological_changes": [],
            "recommendations": {
                "additional_projections": [],
                "follow_up_period": "6 месяцев",
                "specialist_consultation": "не требуется",
            },
            "conclusion": f"УЗИ {organ}: структура и эхогенность в пределах нормы",
            "confidence_level": "высокая",
        }


    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Имитация анализа дерматоскопического изображения"""
        await asyncio.sleep(2)

        return {
            "dermoscopic_features": {
                "asymmetry": {
                    "present": False,
                    "description": "Образование симметричное",
                },
                "border": {
                    "regularity": "ровные",
                    "description": "Границы четкие, ровные",
                },
                "color": {
                    "uniformity": "однородный",
                    "colors_present": ["коричневый"],
                    "description": "Равномерная пигментация",
                },
                "diameter": {"estimated_size": "4 мм", "concerning": False},
                "evolution": {
                    "changes_noted": False,
                    "description": "Изменений не отмечено",
                },
            },
            "risk_assessment": {
                "malignancy_risk": "низкий",
                "abcde_score": "1 балл",
                "concerning_features": [],
            },
            "differential_diagnosis": [
                {
                    "diagnosis": "Доброкачественный невус",
                    "probability": "85%",
                    "supporting_features": [
                        "симметрия",
                        "ровные границы",
                        "однородная окраска",
                    ],
                }
            ],
            "recommendations": {
                "biopsy_needed": False,
                "follow_up_period": "12 месяцев",
                "urgent_referral": False,
            },
            "conclusion": "Дерматоскопические признаки соответствуют доброкачественному невусу",
            "confidence_level": "высокая",
        }


    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Имитация универсального анализа медицинского изображения"""
        await asyncio.sleep(1.5)

        return {
            "image_type": image_type,
            "image_quality": {
                "technical_quality": "хорошая",
                "diagnostic_value": "высокая",
                "limitations": [],
            },
            "pathological_findings": [],
            "normal_findings": ["Структуры в пределах нормы"],
            "differential_diagnosis": ["Норма", "Возрастные изменения"],
            "recommendations": {
                "additional_studies": [],
                "follow_up": "Контроль через 6-12 месяцев",
                "specialist_consultation": "не требуется",
            },
            "conclusion": f"Анализ {image_type}: патологии не выявлено",
            "confidence_level": "средняя",
            "urgent_findings": False,
        }


