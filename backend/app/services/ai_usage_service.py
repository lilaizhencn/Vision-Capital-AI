from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_usage import AIUsageEvent


class AIUsageService:
    """Apply one durable daily quota across every user-facing AI operation."""

    def __init__(self, db: Session):
        self.db = db
        self.zone = ZoneInfo(settings.ai_daily_quota_timezone)

    def snapshot(self, user_id: str, now: datetime | None = None) -> dict:
        local_now = (now or datetime.now(timezone.utc)).astimezone(self.zone)
        usage_date = local_now.date()
        used = self.db.scalar(select(func.count(AIUsageEvent.id)).where(
            AIUsageEvent.user_id == user_id,
            AIUsageEvent.usage_date == usage_date,
        )) or 0
        reset_local = datetime.combine(usage_date + timedelta(days=1), time.min, tzinfo=self.zone)
        limit = settings.ai_daily_quota_limit
        return {
            "usage_date": usage_date,
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "reset_at": reset_local.astimezone(timezone.utc),
            "timezone": settings.ai_daily_quota_timezone,
        }

    def consume(self, user_id: str, category: str, operation_key: str) -> dict:
        if not settings.ai_daily_quota_enabled:
            return self.snapshot(user_id)
        now = datetime.now(timezone.utc)
        usage_date = now.astimezone(self.zone).date()
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            lock_key = f"ai-quota:{user_id}:{usage_date.isoformat()}"
            self.db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": lock_key})
        existing = self.db.scalar(select(AIUsageEvent.id).where(AIUsageEvent.operation_key == operation_key))
        if existing:
            return self.snapshot(user_id, now)
        current = self.snapshot(user_id, now)
        if current["used"] >= current["limit"]:
            self.db.rollback()
            retry_after = max(1, int((current["reset_at"] - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日 AI 体验额度已用完（{current['limit']} 次），请于明日重新使用。",
                headers={
                    "Retry-After": str(retry_after),
                    "X-AI-Limit": str(current["limit"]),
                    "X-AI-Remaining": "0",
                    "X-AI-Reset": current["reset_at"].isoformat(),
                },
            )
        self.db.add(AIUsageEvent(
            user_id=user_id,
            usage_date=usage_date,
            category=category,
            operation_key=operation_key,
        ))
        self.db.commit()
        return self.snapshot(user_id, now)
