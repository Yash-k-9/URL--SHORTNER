from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, SECRET_KEY

# Argon2 is a slow, salted hash designed for passwords: each hash gets a random
# salt (so equal passwords produce different hashes) and is deliberately
# expensive to compute, which makes brute-forcing a leaked database impractical.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # Never compare with ==; verify re-hashes using the salt stored inside `hashed`
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    # A JWT payload is only base64-encoded, so anyone can read it: never put
    # secrets in it. The signature is what stops tampering.
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id from a valid token, or None if it's invalid/expired/tampered."""
    try:
        # jwt.decode checks the signature and the "exp" claim for us
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
