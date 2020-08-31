from app.models.db import TimedBaseModel
from app.models.user import UserRelatedModel


class Message(UserRelatedModel, TimedBaseModel):
    __tablename__ = "messages"
