from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import date

from app.db import models
from app.api import deps
from app.schemas import daily_task as schemas
from app.api.deps import get_current_user

router = APIRouter()


async def get_todays_tasks(db: AsyncSession, user_id: str):
    stmt = select(models.DailyTask).where(
        models.DailyTask.user_id == user_id,
        func.date(models.DailyTask.created_at) == date.today()
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("", response_model=List[schemas.DailyTaskOut])
async def get_daily_tasks(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    tasks = await get_todays_tasks(db, current_user.id)
    return tasks


@router.post("", response_model=schemas.DailyTaskOut)
async def create_daily_task(
    task_in: schemas.DailyTaskCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    db_task = models.DailyTask(
        user_id=current_user.id,
        goal_id=task_in.goal_id,
        title=task_in.title
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


@router.put("/{task_id}/toggle", response_model=schemas.DailyTaskOut)
async def toggle_daily_task(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    result = await db.execute(
        select(models.DailyTask).where(
            models.DailyTask.id == task_id,
            models.DailyTask.user_id == current_user.id
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.completed = not task.completed
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}")
async def delete_daily_task(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    result = await db.execute(
        select(models.DailyTask).where(
            models.DailyTask.id == task_id,
            models.DailyTask.user_id == current_user.id
        )
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted successfully"}
