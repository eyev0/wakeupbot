from app.models.apscheduler import APSchedulerJobsRelatedModel
from app.models.db import TimedBaseModel
from app.models.user import UserRelatedModel


class ReminderJob(APSchedulerJobsRelatedModel, UserRelatedModel, TimedBaseModel):
    __tablename__ = "reminder_jobs"
