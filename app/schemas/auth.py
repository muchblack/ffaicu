from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    id: str = Field(min_length=4, max_length=32, pattern=r"^[a-zA-Z0-9]+$")
    password: str = Field(min_length=4, max_length=32)


class RegisterRequest(BaseModel):
    id: str = Field(min_length=4, max_length=32, pattern=r"^[a-zA-Z0-9]+$")
    password: str = Field(min_length=4, max_length=32)
    password_recovery: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    site_name: str = Field(default="", max_length=128)
    url: str = Field(default="", max_length=256)
    sex: int = Field(default=1, ge=0, le=1)
    image_id: int = Field(default=0, ge=0)
    job_class: int = Field(default=0, ge=0, le=3)  # 初始職業限 0-3


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=4, max_length=32)
    recovery_word: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=4, max_length=32)
    confirm_password: str = Field(min_length=4, max_length=32)
