from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import random

from app.api.deps import get_db
from app.db.models import Quote
from app.schemas.quote import Quote as QuoteSchema

router = APIRouter()

@router.get("/random", response_model=QuoteSchema)
async def get_random_quote(db: AsyncSession = Depends(get_db)):
    # Get total count of quotes
    count_query = select(func.count(Quote.id))
    result = await db.execute(count_query)
    total_quotes = result.scalar()
    
    if total_quotes == 0:
        # Fallback to seeded quotes if table is empty
        fallback_quotes = [
            {"text": "Accountability breeds response-ability.", "author": "Stephen Covey"},
            {"text": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "author": "Aristotle"},
            {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
            {"text": "Success is not final, failure is not fatal: it is the courage to continue that counts.", "author": "Winston Churchill"},
            {"text": "You miss 100% of the shots you don't take.", "author": "Wayne Gretzky"},
            {"text": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius"},
        ]
        quote_data = random.choice(fallback_quotes)
        # Create but don't save to DB
        return {"id": None, "text": quote_data["text"], "author": quote_data["author"], "created_at": None}
    
    # Get a random offset
    random_offset = random.randint(0, total_quotes - 1)
    
    # Get the random quote
    query = select(Quote).offset(random_offset).limit(1)
    result = await db.execute(query)
    quote = result.scalar_one()
    
    return quote

@router.post("/", response_model=QuoteSchema)
async def create_quote(
    quote_data: QuoteSchema,
    db: AsyncSession = Depends(get_db)
):
    quote = Quote(text=quote_data.text, author=quote_data.author)
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote

@router.get("/", response_model=list[QuoteSchema])
async def list_quotes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Quote))
    return result.scalars().all()