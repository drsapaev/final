from pydantic import BaseModel

class Setting(BaseModel):
    key: str
    value: str
    category: str

    class Config:
        orm_mode = True
