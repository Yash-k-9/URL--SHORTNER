from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
import re
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    number: str

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str) -> str:
        if not re.fullmatch(r"^[6-9]\d{9}$", value):
            raise ValueError(
                "Phone number must be a valid 10-digit Indian mobile number."
            )
        return value

class UserCreate(UserBase):
    """Sign-up payload. The password is only ever accepted, never returned."""
    password: str

    @field_validator("password")
    @classmethod
    def password_validator(cls, password):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter.")

        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one digit.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("Password must contain at least one special character.")

        return password

class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

class Url(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:int
    orig_url:str
    short_url:str
    created_at:datetime
    expires_at:datetime | None = None
    user_id:int | None = None

class Click(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:int
    country :str | None = None
    city :str | None = None
    browser :str | None = None
    device :str | None = None
    operating_system :str | None = None
    ip_address :str | None = None
    referrer :str | None = None
    clicked_at :datetime
    url_id:int
