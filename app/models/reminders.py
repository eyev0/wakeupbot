from app.models.apscheduler import APSchedulerJobsRelatedModel
from app.models.db import TimedBaseModel
from app.models.user import UserRelatedModel


class BedtimeReminder(APSchedulerJobsRelatedModel, UserRelatedModel, TimedBaseModel):
    __tablename__ = "bedtime_reminders"


class WakeupReminder(APSchedulerJobsRelatedModel, UserRelatedModel, TimedBaseModel):
    __tablename__ = "wakeup_reminders"
