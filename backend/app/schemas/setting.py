from app.schemas.base import ORMModel


class Setting(ORMModel):
    key: str
    value: str
    category: str
