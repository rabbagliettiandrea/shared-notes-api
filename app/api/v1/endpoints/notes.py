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


async def get_shared_with_usernames(note_id: int, owner_id: int, db: AsyncSession) -> List[str]:
    """Get list of usernames who have access to a note (excluding the owner)"""
    from app.models.user import User
    
    result = await db.execute(
        select(User.username)
        .join(NoteShare)
        .where(and_(NoteShare.note_id == note_id, User.id != owner_id))
    )
    usernames = [row[0] for row in result.fetchall()]
    return usernames


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
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .where(Note.id == db_note.id)
    )
    note_with_tags = result.scalar_one()
    
    # Convert tags back to names for response
    note_response = NoteResponse(
        id=note_with_tags.id,
        title=note_with_tags.title,
        content=note_with_tags.content,
        tags=tags_to_names(note_with_tags.tags),
        owner_id=note_with_tags.owner_id,
        owner_username=current_user.username,
        shared_with=[],  # New note, not shared with anyone yet
        created_at=note_with_tags.created_at,
        updated_at=note_with_tags.updated_at
    )
    return note_response


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: str = Query(None, description="Search text in title and content"),
    tags: str = Query(None, description="Comma-separated list of tag names to filter by"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notes and notes shared with user with optional search and tag filtering"""
    
    # Build base query for user's own notes
    own_notes_query = (
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .where(Note.owner_id == current_user.id)
    )
    
    # Build base query for shared notes
    shared_notes_query = (
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .join(NoteShare)
        .where(NoteShare.user_id == current_user.id)
    )
    
    # Apply text search filter if provided
    if search:
        search_filter = or_(
            Note.title.ilike(f"%{search}%"),
            Note.content.ilike(f"%{search}%")
        )
        own_notes_query = own_notes_query.where(search_filter)
        shared_notes_query = shared_notes_query.where(search_filter)
    
    # Apply tag filter if provided
    if tags:
        tag_names = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if tag_names:
            # Join with tags table and filter by tag names
            own_notes_query = (
                own_notes_query
                .join(Note.tags)
                .where(Tag.name.in_(tag_names))
                .distinct()
            )
            shared_notes_query = (
                shared_notes_query
                .join(Note.tags)
                .where(Tag.name.in_(tag_names))
                .distinct()
            )
    
    # Apply pagination
    own_notes_query = own_notes_query.offset(skip).limit(limit)
    shared_notes_query = shared_notes_query.offset(skip).limit(limit)
    
    # Execute queries
    result = await db.execute(own_notes_query)
    own_notes = result.scalars().all()
    
    result = await db.execute(shared_notes_query)
    shared_notes = result.scalars().all()
    
    # Combine and return unique notes
    all_notes = list(own_notes) + list(shared_notes)
    unique_notes = list({note.id: note for note in all_notes}.values())
    
    # Convert to response format with tags as names
    note_responses = []
    for note in unique_notes:
        # Get shared with usernames for each note (excluding owner)
        shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
        
        note_response = NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            owner_username=note.owner.username if note.owner else None,
            shared_with=shared_with,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        note_responses.append(note_response)
    
    return note_responses




@router.get("/search", response_model=List[NoteResponse])
async def search_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: str = Query(None, description="Search text in title and content"),
    tags: str = Query(None, description="Comma-separated list of tag names to filter by"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Advanced search for notes with multiple filters"""
    
    # Build base query for user's accessible notes (own + shared)
    query = (
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .outerjoin(NoteShare, and_(Note.id == NoteShare.note_id, NoteShare.user_id == current_user.id))
        .where(
            or_(
                Note.owner_id == current_user.id,  # User's own notes
                NoteShare.user_id == current_user.id,  # Notes shared with user
            )
        )
    )
    
    # Apply text search filter if provided
    if search:
        search_filter = or_(
            Note.title.ilike(f"%{search}%"),
            Note.content.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    # Apply tag filter if provided
    if tags:
        tag_names = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if tag_names:
            # Join with tags table and filter by tag names
            query = (
                query
                .join(Note.tags)
                .where(Tag.name.in_(tag_names))
                .distinct()
            )
    
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    notes = result.scalars().all()
    
    # Convert to response format with tags as names
    note_responses = []
    for note in notes:
        # Get shared with usernames for each note (excluding owner)
        shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
        
        note_response = NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            owner_username=note.owner.username if note.owner else None,
            shared_with=shared_with,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        note_responses.append(note_response)
    
    return note_responses


@router.get("/tags", response_model=List[str])
async def get_all_tags(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all available tags from user's own notes only"""
    
    # Get tags only from user's own notes
    query = (
        select(Tag.name)
        .join(Note.tags)
        .where(Note.owner_id == current_user.id)  # Only user's own notes
        .distinct()
        .order_by(Tag.name)
    )
    
    result = await db.execute(query)
    tag_names = [row[0] for row in result.fetchall()]
    
    return tag_names


@router.get("/shared", response_model=List[NoteResponse])
async def get_shared_notes(
    skip: int = Query(0, ge=0, description="Number of notes to skip"),
    limit: int = Query(100, ge=1, le=100, description="Number of notes to return"),
    search: str = Query(None, description="Search text in title and content"),
    tags: str = Query(None, description="Comma-separated list of tag names to filter by"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notes shared with the current user"""
    
    # Build base query for shared notes only
    query = (
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .join(NoteShare)
        .where(NoteShare.user_id == current_user.id)
    )
    
    # Apply search filter if provided
    if search:
        search_filter = or_(
            Note.title.ilike(f"%{search}%"),
            Note.content.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    # Apply tag filter if provided
    if tags:
        tag_names = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if tag_names:
            query = (
                query
                .join(Note.tags)
                .where(Tag.name.in_(tag_names))
                .distinct()
            )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    notes = result.scalars().all()
    
    # Convert to response format with tags as names
    note_responses = []
    for note in notes:
        # Get shared with usernames for each note (excluding owner)
        shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
        
        note_response = NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            owner_username=note.owner.username if note.owner else None,
            shared_with=shared_with,
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
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        # Get shared with usernames for this note (excluding owner)
        shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
        
        return NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            owner_username=note.owner.username if note.owner else None,
            shared_with=shared_with,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
    
    # Check if note is shared with user
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .join(NoteShare)
        .where(and_(Note.id == note_id, NoteShare.user_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if note:
        # Get shared with usernames for this note (excluding owner)
        shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
        
        return NoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            tags=tags_to_names(note.tags),
            owner_id=note.owner_id,
            owner_username=note.owner.username if note.owner else None,
            shared_with=shared_with,
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
    """Update a note (only owner)"""
    # Check if user owns the note
    result = await db.execute(
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.owner))
        .where(and_(Note.id == note_id, Note.owner_id == current_user.id))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non hai i permessi sufficienti per aggiornare questa nota"
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
    shared_with = await get_shared_with_usernames(note.id, note.owner_id, db)
    
    note_response = NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        tags=tags_to_names(note.tags),
        owner_id=note.owner_id,
        owner_username=note.owner.username if note.owner else None,
        shared_with=shared_with,
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
    user_id: int = Query(..., description="ID of the user to share the note with"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Share a note with another user (only owner) - read-only access"""
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
        # Note is already shared, no need to do anything
        return {"message": f"Nota già condivisa con l'utente {user_id}"}
    else:
        # Create new share (read-only by default)
        note_share = NoteShare(
            note_id=note_id,
            user_id=user_id
        )
        db.add(note_share)
    
    await db.commit()
    
    return {"message": f"Nota condivisa con l'utente {user_id}"}


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

