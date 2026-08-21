"""JWT + bcrypt authentication helpers."""
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-prod-super-secret-key")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24 * 7  # 7 days

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Dependency that returns the current user dict from Mongo."""
    from server import db  # avoid circular import

    if credentials is None:
        raise HTTPException(status_code=401, detail="لم يتم تسجيل الدخول")
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="جلسة غير صالحة")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")
    if user.get("status") in ("SUSPENDED", "BANNED"):
        raise HTTPException(status_code=403, detail="تم إيقاف الحساب")
    return user


async def get_user_from_token_str(token: str):
    """For WebSocket auth via query param."""
    from server import db

    user_id = decode_token(token)
    if not user_id:
        return None
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user or user.get("status") in ("SUSPENDED", "BANNED"):
        return None
    return user
