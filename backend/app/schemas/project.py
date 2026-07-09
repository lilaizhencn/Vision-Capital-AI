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


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

