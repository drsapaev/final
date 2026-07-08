"""Imaging mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    OpenAIProviderMixinBase,
    AIRequest,
    AIResponse,
    json,
    logging,
    Any,
    base64,
)


class ImagingMixin(OpenAIProviderMixinBase):
    """Imaging methods for OpenAIProvider."""

    async def analyze_xray_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ рентгеновского снимка"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        body_part = (
            metadata.get("body_part", "не указано") if metadata else "не указано"
        )
        patient_age = (
            metadata.get("patient_age", "не указан") if metadata else "не указан"
        )
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
                    {
                        "role": "system",
                        "content": "Вы опытный врач-рентгенолог. Анализируете снимки с высокой точностью. Ответы только в формате JSON.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}


    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ УЗИ изображения"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        organ = metadata.get("organ", "не указан") if metadata else "не указан"
        patient_age = (
            metadata.get("patient_age", "не указан") if metadata else "не указан"
        )

        prompt = f"""Проанализируйте ультразвуковое изображение как врач УЗИ-диагностики.

        Исследуемый орган: {organ}
        Возраст пациента: {patient_age}

        Предоставьте анализ в формате JSON с качеством изображения, анатомической оценкой, патологическими изменениями и рекомендациями."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Вы опытный врач УЗИ-диагностики. Анализируете изображения с учетом технических параметров. Ответы только в формате JSON.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}


    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: dict | None = None
    ) -> dict[str, Any]:
        """Анализ дерматоскопического изображения"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        lesion_location = (
            metadata.get("lesion_location", "не указана") if metadata else "не указана"
        )
        patient_age = (
            metadata.get("patient_age", "не указан") if metadata else "не указан"
        )

        prompt = f"""Проанализируйте дерматоскопическое изображение как дерматолог-онколог.

        Локализация образования: {lesion_location}
        Возраст пациента: {patient_age}

        Проведите анализ по системе ABCDE и предоставьте результат в формате JSON с дерматоскопическими признаками, оценкой риска, дифференциальной диагностикой и рекомендациями."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Вы опытный дерматолог-онколог с экспертизой в дерматоскопии. Анализируете по стандартам ABCDE. Ответы только в формате JSON.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=2500,
                temperature=0.1,
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}


    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: dict | None = None
    ) -> dict[str, Any]:
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
                    {
                        "role": "system",
                        "content": f"Вы опытный врач-специалист по анализу медицинских изображений типа {image_type}. Ответы только в формате JSON.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": self._format_error(e)}


