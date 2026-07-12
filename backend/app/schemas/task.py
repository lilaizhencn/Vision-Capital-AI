from datetime import datetime

from pydantic import BaseModel, Field


class TaskRead(BaseModel):
    id: str
    project_id: str
    label: str
    done: bool
    status: str
    description: str
    assignee: str
    due_date: datetime | None
    result: str
    related_requirement_id: str | None
    evidence_file_ids: list[str]
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    status: str = Field(default="todo", pattern=r"^(todo|in_progress|completed)$")
    description: str = Field(default="", max_length=5000)
    assignee: str = Field(default="", max_length=120)
    due_date: datetime | None = None
    result: str = Field(default="", max_length=20_000)
    related_requirement_id: str | None = None
    evidence_file_ids: list[str] = Field(default_factory=list, max_length=50)


class TaskUpdate(BaseModel):
    done: bool | None = None
    status: str | None = Field(default=None, pattern=r"^(todo|in_progress|completed)$")
    label: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assignee: str | None = Field(default=None, max_length=120)
    due_date: datetime | None = None
    result: str | None = Field(default=None, max_length=20_000)
    related_requirement_id: str | None = None
    evidence_file_ids: list[str] | None = Field(default=None, max_length=50)
