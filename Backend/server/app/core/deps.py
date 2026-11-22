import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import ApiError
from app.db import get_db
from app.models import User


def optional_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User | None:
    if not authorization:
        return None
    return _load_user(authorization, db)


def current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization:
        raise ApiError(401, "UNAUTHORIZED", "Vui lòng đăng nhập")
    user = _load_user(authorization, db)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Phiên đăng nhập không hợp lệ")
    return user


def _load_user(authorization: str, db: Session) -> User | None:
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (ValueError, KeyError, TypeError, jwt.PyJWTError):
        raise ApiError(401, "UNAUTHORIZED", "Phiên đăng nhập không hợp lệ") from None
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Phiên đăng nhập không hợp lệ")
    if user.is_banned:
        raise ApiError(
            403, "BANNED", f"Tài khoản đã bị khóa: {user.ban_reason or 'Không có lý do'}"
        )
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise ApiError(403, "FORBIDDEN", "Bạn không có quyền thực hiện thao tác này")
    return user
