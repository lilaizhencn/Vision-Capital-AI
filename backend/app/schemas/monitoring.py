from datetime import datetime

from pydantic import BaseModel, Field


class MonitoringUpdateCreate(BaseModel):
    metric_name: str = Field(min_length=1, max_length=120)
    metric_value: str = Field(min_length=1, max_length=120)
    metric_unit: str = Field(default="", max_length=40)
    risk_level: str = Field(default="normal", pattern="^(normal|watch|high)$")
    note: str = Field(default="", max_length=5000)


class MonitoringUpdateRead(MonitoringUpdateCreate):
    id: str
    project_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
