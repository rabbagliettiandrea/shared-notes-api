from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.note import Note
from app.models.note_share import NoteShare
from app.schemas.note import NoteCreate, NoteUpdate, NoteResponse

router = APIRouter()


@router.post("/", response_model=NoteResponse)
async def create_note(
    note: NoteCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new note"""
    db_note = Note(
        title=note.title,
        content=note.content,
        is_public=note.is_public,
        owner_id=current_user.id
    )
    db.add(db_note)
    await db.commit()
    await db.refresh(db_note)
    return db_note


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notes and notes shared with user"""
    # Get user's own notes
    result = await db.execute(
        select(Note)
        .where(Note.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    own_notes = result.scalars().all()
    
    # Get notes shared with user
    result = await db.execute(
        select(Note)
        .join(NoteShare)
        .where(NoteShare.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    shared_notes = result.scalars().all()
    
    # Combine and return unique notes
    all_notes = list(own_notes) + list(shared_notes)
    unique_notes = list({note.id: note for note in all_notes}.values())
    
    return unique_notes


@router.get("/public", response_model=List[NoteResponse])
async def get_public_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get all public notes"""
    result = await db.execute(
        select(Note)
        .where(Note.is_public == True)
        .offset(skip)
        .limit(limit)
    )
    notes = result.scalars().all()
    return notes


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific note by ID"""
    # Check if user owns the note
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return note
    
    # Check if note is shared with user
    result = await db.execute(
        select(Note)
        .join(NoteShare)
        .where(and_(Note.id == note_id, NoteShare.user_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return note
    
    # Check if note is public
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.is_public == True))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return note
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Note not found"
    )


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    note_update: NoteUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a note (only owner or users with write permission)"""
    # Check if user owns the note
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        # Check if user has write permission
        result = await db.execute(
            select(NoteShare)
            .where(and_(
                NoteShare.note_id == note_id,
                NoteShare.user_id == current_user.id,
                or_(NoteShare.permission == "write", NoteShare.permission == "admin")
            ))
        )
        share = result.scalar_one_or_none()
        
        if not share:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to update this note"
            )
        
        # Get the note
        result = await db.execute(select(Note).where(Note.id == note_id))
        note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Update note fields
    update_data = note_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a note (only owner)"""
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found or you don't have permission to delete it"
        )
    
    await db.delete(note)
    await db.commit()
    
    return {"message": "Note deleted successfully"}


@router.post("/{note_id}/share")
async def share_note(
    note_id: int,
    user_id: int,
    permission: str = Query("read", regex="^(read|write|admin)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Share a note with another user (only owner)"""
    # Check if current user owns the note
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found or you don't have permission to share it"
        )
    
    # Check if target user exists
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )
    
    # Check if note is already shared with this user
    result = await db.execute(
        select(NoteShare).where(
            and_(NoteShare.note_id == note_id, NoteShare.user_id == user_id)
        )
    )
    existing_share = result.scalar_one_or_none()
    
    if existing_share:
        # Update existing share
        existing_share.permission = permission
    else:
        # Create new share
        note_share = NoteShare(
            note_id=note_id,
            user_id=user_id,
            permission=permission
        )
        db.add(note_share)
    
    await db.commit()
    
    return {"message": f"Note shared with user {user_id} with {permission} permission"}


@router.delete("/{note_id}/share/{user_id}")
async def unshare_note(
    note_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove sharing of a note with a user (only owner)"""
    # Check if current user owns the note
    result = await db.execute(
        select(Note).where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found or you don't have permission to unshare it"
        )
    
    # Find and delete the share
    result = await db.execute(
        select(NoteShare).where(
            and_(NoteShare.note_id == note_id, NoteShare.user_id == user_id)
        )
    )
    note_share = result.scalar_one_or_none()
    
    if not note_share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found"
        )
    
    await db.delete(note_share)
    await db.commit()
    
    return {"message": f"Note unshared with user {user_id}"}
