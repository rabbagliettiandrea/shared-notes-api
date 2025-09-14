from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class NoteBase(BaseModel):
    title: str
    content: Optional[str] = None
    tags: Optional[List[str]] = []


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class NoteResponse(NoteBase):
    id: int
    owner_id: int
    owner_username: Optional[str] = None
    shared_with: Optional[List[str]] = []  # List of usernames who have access to this note (excluding owner)
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
