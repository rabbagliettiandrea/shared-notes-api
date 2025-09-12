from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class NoteBase(BaseModel):
    title: str
    content: Optional[str] = None
    is_public: bool = False


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_public: Optional[bool] = None


class NoteResponse(NoteBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
