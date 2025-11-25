from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class QuoteBase(BaseModel):
    text: str
    author: str

class QuoteCreate(QuoteBase):
    pass

class Quote(QuoteBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True