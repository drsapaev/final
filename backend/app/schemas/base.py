from pydantic import BaseModel

class ORMModel(BaseModel):
    # Pydantic v2 аналог Config.orm_mode = True
    model_config = {
        "from_attributes": True
    }
