import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(hashlib.sha256(password.encode()).digest(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(hashlib.sha256(password.encode()).digest(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(days=7)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
