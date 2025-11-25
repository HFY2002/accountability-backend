from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api import deps
from app.schemas import goal_category as schemas
from app.db import models

router = APIRouter()


@router.get("", response_model=List[schemas.GoalCategoryOut])
async def list_categories(
    db: AsyncSession = Depends(deps.get_db),
):
    """List all goal categories"""
    stmt = select(models.GoalCategory).order_by(models.GoalCategory.name)
    
    result = await db.execute(stmt)
    categories = result.scalars().all()
    return categories
