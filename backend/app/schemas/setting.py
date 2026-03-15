from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class Setting(ORMModel):
    key: str
    value: str | None
    category: str


class SettingUpsert(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=500)
