from dataclasses import dataclass

from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher.handler import ctx_data
from sqlalchemy import and_

from app.models.sleep_record import SleepRecord
from app.models.user import User


@dataclass
class UserAwakeFilter(BoundFilter):
    key = "user_awake"
    user_awake: bool

    async def check(self, obj) -> bool:
        data = ctx_data.get()
        user: User = data["user"]
        record = await SleepRecord.query.where(
            and_(
                SleepRecord.user_id == user.id,
                SleepRecord.check_wakeup == False,  # noqa
            )
        ).gino.first()
        return (record is None) == self.user_awake
