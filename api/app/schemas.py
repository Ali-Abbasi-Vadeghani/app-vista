from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    package_name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)

    @field_validator("name", "package_name", "category")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value


class ApplicationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    package_name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)

    @field_validator("name", "package_name", "category")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    package_name: str
    category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime