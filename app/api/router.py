from fastapi import APIRouter

from app.api.routes import (
    auth,
    categories,
    city,
    companies,
    friends,
    leaderboard,
    notifications,
    paired_tasks,
    posts,
    time_entries,
    users,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(time_entries.router)
api_router.include_router(city.router)
api_router.include_router(friends.router)
api_router.include_router(paired_tasks.router)
api_router.include_router(posts.router)
api_router.include_router(notifications.router)
api_router.include_router(companies.router)
api_router.include_router(leaderboard.router)
api_router.include_router(ws.router)
