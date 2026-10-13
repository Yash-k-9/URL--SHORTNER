import secrets
import string
from datetime import datetime, timezone

def generate_short_code(length: int = 6) -> str:
    """Generate a random, unpredictable short code."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def utcnow() -> datetime:
    """Current UTC time as a naive datetime (matches the existing DateTime columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
