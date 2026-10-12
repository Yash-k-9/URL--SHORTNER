from pydantic import BaseModel,EmailStr,field_validator
import re
from datetime import datetime

class User(BaseModel):
    id: int
    name: str
    email: EmailStr
    number: str
    Pass: str

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str) -> str:
        if not re.fullmatch(r"^[6-9]\d{9}$", value):
            raise ValueError(
                "Phone number must be a valid 10-digit Indian mobile number."
            )
        return value

    
    @field_validator("Pass")
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

class Url(BaseModel):
    id:int
    orig_url:str
    short_url:str
    created_at:datetime
    expires_at:datetime
    user_id:int
    
class Click(BaseModel):
    id:int
    country :str
    city :str
    browser :str
    device :str
    operating_system :str
    ip_address :str
    referrer :str
    clicked_at :datetime
    url_id:int