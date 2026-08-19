from fastapi import APIRouter

from app.api.routes import auth, categories, city, friends, paired_tasks, time_entries, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(time_entries.router)
api_router.include_router(city.router)
api_router.include_router(friends.router)
api_router.include_router(paired_tasks.router)
