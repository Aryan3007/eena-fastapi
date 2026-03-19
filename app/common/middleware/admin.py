from fastapi import HTTPException, Request, status

from app.config.settings import settings


async def verify_admin(request: Request) -> None:
    secret = request.headers.get("x-admin-secret", "")
    if secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin secret")
