from __future__ import annotations

from app.models.db import BaseModel, TimedBaseModel, db
from app.models.user import UserRelatedModel


class SleepRecord(UserRelatedModel, TimedBaseModel):
    __tablename__ = "sleep_records"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    wakeup_time = db.Column(db.DateTime(True))
    mood = db.Column(db.String)
    emoji = db.Column(db.String)
    note = db.Column(db.String)


class SleepRecordRelatedModel(BaseModel):
    __abstract__ = True

    sleep_record_id = db.Column(
        db.ForeignKey(
            f"{SleepRecord.__tablename__}.id", ondelete="CASCADE", onupdate="CASCADE"
        ),
        nullable=False,
    )
