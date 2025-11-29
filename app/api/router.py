from fastapi import APIRouter
from app.api import goals, proofs, social, auth, users, daily_tasks, categories, templates, quotes, goal_viewers, notifications

api_router = APIRouter()

# Add endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(goal_viewers.router, prefix="", tags=["goal_viewers"])  # Already includes /goals prefix
api_router.include_router(proofs.router, prefix="/proofs", tags=["proofs"])
api_router.include_router(social.router, prefix="/friends", tags=["social"])
api_router.include_router(daily_tasks.router, prefix="/daily-tasks", tags=["daily_tasks"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(notifications.router, prefix="", tags=["notifications"])  # Notifications endpoints
