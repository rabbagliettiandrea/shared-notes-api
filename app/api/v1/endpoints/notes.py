from typing import List
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.note import Note
from app.models.note_share import NoteShare
from app.models.tag import Tag
from app.models.note_tag import note_tags
from app.schemas.note import NoteCreate, NoteUpdate, NoteResponse

router = APIRouter()


async def get_or_create_tags(tag_names: List[str], db: AsyncSession) -> List[Tag]:
    """Get existing tags or create new ones"""
    if not tag_names:
        return []
    
    tags = []
    for tag_name in tag_names:
        tag_name = tag_name.strip().lower()
        if not tag_name:
            continue
            
        # Try to get existing tag
        result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = result.scalar_one_or_none()
        
        if not tag:
            # Create new tag
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()  # Flush to get the ID
        
        tags.append(tag)
    
    return tags


def tags_to_names(tags) -> List[str]:
    """Convert Tag objects to list of tag names"""
    if not tags:
        return []
    
    # Convert SQLAlchemy relationship to list of tag names
    return [tag.name for tag in tags]


@router.post("/", response_model=NoteResponse)
async def create_note(
    note: NoteCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new note"""
    # Get or create tags
    tag_objects = await get_or_create_tags(note.tags or [], db)
    
    # Create note
    db_note = Note(
        title=note.title,
        content=note.content,
        is_public=note.is_public,
        owner_id=current_user.id
    )
    
    # Associate tags with note
    db_note.tags = tag_objects
    
    db.add(db_note)
    await db.commit()
    await db.refresh(db_note)
    
    # Reload the note with tags to avoid lazy loading issues
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.id == db_note.id)
    )
    note_with_tags = result.scalar_one()
    
    # Convert tags back to names for response
    note_response = NoteResponse(
        id=note_with_tags.id,
        title=note_with_tags.title,
        content=note_with_tags.content,
        is_public=note_with_tags.is_public,
        tags=tags_to_names(note_with_tags.tags),
        owner_id=note_with_tags.owner_id,
        created_at=note_with_tags.created_at,
        updated_at=note_with_tags.updated_at
    )
    return note_response


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notes and notes shared with user"""
    # Get user's own notes with tags
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    own_notes = result.scalars().all()
    
    # Get notes shared with user with tags
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .join(NoteShare)
        .where(NoteShare.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    shared_notes = result.scalars().all()
    
    # Combine and return unique notes
    all_notes = list(own_notes) + list(shared_notes)
    unique_notes = list({note.id: note for note in all_notes}.values())
    
    # Convert to response format with tags as names
    note_responses = []
    for note in unique_notes:
        note_response = NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        note_responses.append(note_response)
    
    return note_responses


@router.get("/public", response_model=List[NoteResponse])
async def get_public_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get all public notes"""
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.is_public == True)
        .offset(skip)
        .limit(limit)
    )
    notes = result.scalars().all()
    
    # Convert to response format with tags as names
    note_responses = []
    for note in notes:
        note_response = NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        note_responses.append(note_response)
    
    return note_responses


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific note by ID"""
    # Check if user owns the note
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
    
    # Check if note is shared with user
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .join(NoteShare)
        .where(and_(Note.id == note_id, NoteShare.user_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
    
    # Check if note is public
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags))
        .where(and_(Note.id == note_id, Note.is_public == True))
    )
    note = result.scalar_one_or_none()
    
    if note:
        return NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            is_public=note.is_public,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
    
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
        select(Note)
        .options(selectinload(Note.tags))
        .where(and_(Note.id == note_id, Note.owner_id == current_user.id))
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
                detail="Non hai i permessi sufficienti per aggiornare questa nota"
            )
        
        # Get the note
        result = await db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id)
        )
        note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Update note fields
    update_data = note_update.dict(exclude_unset=True)
    
    # Handle tags separately
    if 'tags' in update_data:
        tag_objects = await get_or_create_tags(update_data['tags'] or [], db)
        note.tags = tag_objects
        del update_data['tags']
    
    # Update other fields
    for field, value in update_data.items():
        setattr(note, field, value)
    
    await db.commit()
    await db.refresh(note)
    
    # Return response with tags as names
    note_response = NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        is_public=note.is_public,
        tags=tags_to_names(note.tags),
        owner_id=note.owner_id,
        created_at=note.created_at,
        updated_at=note.updated_at
    )
    return note_response


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
            detail="Nota non trovata o non hai i permessi per eliminarla"
        )
    
    await db.delete(note)
    await db.commit()
    
    return {"message": "Nota eliminata con successo"}


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
            detail="Nota non trovata o non hai i permessi per condividere la nota"
        )
    
    # Check if target user exists
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato"
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
    
    return {"message": f"Nota condivisa con l'utente {user_id} con permesso {permission}"}


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
            detail="Nota non trovata o non hai i permessi per smettere di condividere la nota"
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
            detail="Condivisione non trovata"
        )
    
    await db.delete(note_share)
    await db.commit()
    
    return {"message": f"Nota smessa di essere condivisa con l'utente {user_id}"}
