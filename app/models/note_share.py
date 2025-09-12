from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class NoteShare(Base):
    __tablename__ = "note_shares"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String(20), default="read")  # read, write, admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    note = relationship("Note", back_populates="shared_with")
    user = relationship("User", back_populates="shared_notes")
