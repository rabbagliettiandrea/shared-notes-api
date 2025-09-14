from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


@router.get("/search", response_model=List[UserResponse])
async def search_users(
    query: str = Query(..., description="Search text in username"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search users by username"""
    if not query or len(query.strip()) < 2:
        return []
    
    search_term = f"%{query.strip()}%"
    
    # Search in username only
    result = await db.execute(
        select(User).where(
            and_(
                User.is_active == True,  # Only active users
                User.id != current_user.id,  # Exclude current user
                User.username.ilike(search_term)
            )
        ).limit(10)  # Limit results to 10 users
    )
    
    users = result.scalars().all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato"
        )
    
    return user
