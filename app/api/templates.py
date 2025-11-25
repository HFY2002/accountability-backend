from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import json

from app.api import deps
from app.schemas import goal_template as schemas
from app.db import models

router = APIRouter()


@router.get("", response_model=List[schemas.GoalTemplateOut])
async def list_templates(
    db: AsyncSession = Depends(deps.get_db),
):
    """List all goal templates"""
    stmt = select(models.GoalTemplate).order_by(models.GoalTemplate.title)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    # Convert the JSON string milestones to Python list
    response_templates = []
    for template in templates:
        template_dict = {}
        for key, value in template.__dict__.items():
            if key == 'milestones' and value:
                try:
                    template_dict[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    template_dict[key] = []
            else:
                template_dict[key] = value
        response_templates.append(template_dict)
    
    return response_templates


@router.post("", response_model=schemas.GoalTemplateOut, status_code=201)
async def create_template(
    template_in: schemas.GoalTemplateIn,
    db: AsyncSession = Depends(deps.get_db),
):
    """Create a new goal template (admin only - placeholder for future)"""
    # Convert milestones list to JSON string
    milestones_json = json.dumps(template_in.milestones)
    
    template = models.GoalTemplate(
        title=template_in.title,
        description=template_in.description,
        category_id=template_in.category_id,
        image_url=template_in.image_url,
        milestones=milestones_json
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    # Convert for response
    template.milestones = json.loads(milestones_json)
    return template


@router.get("/{template_id}", response_model=schemas.GoalTemplateOut)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get a specific template by ID"""
    stmt = select(models.GoalTemplate).where(models.GoalTemplate.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Convert milestones JSON string to list
    if template.milestones:
        try:
            template.milestones = json.loads(template.milestones)
        except (json.JSONDecodeError, TypeError):
            template.milestones = []
    else:
        template.milestones = []
    
    return template
