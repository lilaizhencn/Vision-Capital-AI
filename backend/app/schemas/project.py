from datetime import datetime

from pydantic import BaseModel

from app.models.project import InvestmentStatus


class ProjectBase(BaseModel):
    name: str
    company_name: str
    industry: str
    stage: str
    description: str = ""
    investment_status: InvestmentStatus = InvestmentStatus.pre_investment
    research_auto_enabled: bool = True


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    research_status: str
    last_research_at: datetime | None
    next_research_at: datetime | None
    research_last_error: str | None

    model_config = {"from_attributes": True}
