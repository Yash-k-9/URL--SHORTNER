from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import create_access_token, decode_access_token, hash_password, verify_password
from database import get_db
from databse_models import User
from models import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Reads "Authorization: Bearer <token>" and powers the Authorize button in /docs.
# auto_error=False lets get_optional_user allow anonymous requests.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_optional_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User | None:
    """The logged-in user, or None for anonymous requests. Invalid tokens are rejected."""
    if token is None:
        return None
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        # A token was sent but is expired, tampered with, or for a deleted user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Add `user: User = Depends(get_current_user)` to a route to require login."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=email,
        number=payload.number,
        Pass=hash_password(payload.password),  # store the hash, never the password
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two sign-ups with the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(user)
    return user  # UserOut has no password field, so it can't leak


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2's form calls the field "username"; we put the email in it
    user = db.query(User).filter(User.email == form.username.lower()).first()

    # Same error for "no such email" and "wrong password", so attackers
    # can't use this endpoint to discover which emails are registered
    if user is None or not verify_password(form.password, user.Pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
