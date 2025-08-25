from pydantic import BaseModel

class SettingSchema(BaseModel):
    id: int
    category: str
    key: str
    value: str

    class Config:
        from_attributes = True  # SQLAlchemy ORM compatibility (Pydantic v2)
