from datetime import datetime

from pydantic import BaseModel, Field


class TaskRead(BaseModel):
    id: str
    project_id: str
    label: str
    done: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    done: bool = Field(default=False)
