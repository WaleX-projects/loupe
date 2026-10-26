import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    owner_id: uuid.UUID

class ProjectUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    status: str | None = Field(None, max_length=30)

class ProjectResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True