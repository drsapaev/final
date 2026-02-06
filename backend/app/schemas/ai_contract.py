"""
AI Response Contract - единый формат ответов AI подсистемы

Все AI ответы должны проходить через эти модели для обеспечения
совместимости между backend и frontend.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AISuggestion(BaseModel):
    """Единичная подсказка от AI"""
    
    id: str = Field(..., description="Уникальный ID подсказки")
    text: str = Field(..., description="Текст подсказки для отображения")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Уверенность модели (0.0-1.0)"
    )
    source: Literal["ai", "history", "template"] = Field(
        default="ai",
        description="Источник подсказки"
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные данные (код МКБ, категория и т.д.)"
    )


class AIICD10Suggestion(BaseModel):
    """Подсказка кода МКБ-10"""
    
    code: str = Field(..., description="Код МКБ-10 (например, R50.9)")
    label: str = Field(..., description="Описание кода")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Уверенность модели"
    )
    category: Optional[str] = Field(
        default=None,
        description="Категория (respiratory, cardiovascular, etc.)"
    )


class AIResponse(BaseModel):
    """Стандартный ответ AI подсистемы"""
    
    status: Literal["success", "error"] = Field(..., description="Статус ответа")
    suggestions: List[AISuggestion] = Field(
        default_factory=list,
        description="Список подсказок"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Имя провайдера (deepseek, openai, gemini)"
    )
    latency_ms: Optional[int] = Field(
        default=None,
        description="Время выполнения в миллисекундах"
    )
    error: Optional[str] = Field(
        default=None,
        description="Сообщение об ошибке (если status=error)"
    )
    debug_meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Отладочная информация (только в dev режиме)"
    )


class AIICD10Response(BaseModel):
    """Ответ с подсказками МКБ-10"""
    
    status: Literal["success", "error"] = Field(..., description="Статус ответа")
    suggestions: List[AIICD10Suggestion] = Field(
        default_factory=list,
        description="Список кодов МКБ-10"
    )
    provider: Optional[str] = Field(default=None)
    latency_ms: Optional[int] = Field(default=None)
    error: Optional[str] = Field(default=None)
    debug_meta: Optional[Dict[str, Any]] = Field(default=None)

    def to_generic_suggestions(self) -> List[AISuggestion]:
        """Преобразовать в универсальный формат AISuggestion"""
        return [
            AISuggestion(
                id=s.code,
                text=f"{s.code} - {s.label}",
                confidence=s.confidence,
                source="ai",
                meta={"code": s.code, "label": s.label, "category": s.category}
            )
            for s in self.suggestions
        ]


class AIComplaintAnalysis(BaseModel):
    """Результат анализа жалоб"""
    
    status: Literal["success", "error"] = Field(...)
    preliminary_diagnosis: List[str] = Field(default_factory=list)
    examinations: List[Dict[str, str]] = Field(default_factory=list)
    lab_tests: List[str] = Field(default_factory=list)
    consultations: List[str] = Field(default_factory=list)
    urgency: Optional[str] = Field(default="планово")
    red_flags: List[str] = Field(default_factory=list)
    treatment_suggestion: Optional[str] = Field(default=None)
    examination_plan: Optional[str] = Field(default=None)
    recommendations: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    latency_ms: Optional[int] = Field(default=None)
    error: Optional[str] = Field(default=None)
    debug_meta: Optional[Dict[str, Any]] = Field(default=None)
