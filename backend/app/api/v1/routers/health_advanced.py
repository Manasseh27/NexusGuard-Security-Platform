"""Advanced health endpoints."""
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

@router.get("/platform")
async def platform_health():
    from app.infrastructure.database.session import check_db_health
    from app.infrastructure.cache.redis_client import check_redis_health
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    return {
        "status": "healthy" if db_ok and redis_ok else "degraded",
        "components": {"database": db_ok, "cache": redis_ok},
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.get("")
async def health_root():
    return await platform_health()
