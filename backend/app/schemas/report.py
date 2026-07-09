from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: str
    project_id: str
    title: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

