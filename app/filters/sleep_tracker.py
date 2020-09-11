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
    user: User = None

    async def check(self, obj=None) -> bool:
        if not self.user:
            data = ctx_data.get()
            self.user: User = data["user"]
        record = await SleepRecord.query.where(
            and_(
                SleepRecord.user_id == self.user.id,
                SleepRecord.wakeup_time == None,  # noqa
            )
        ).gino.first()
        return (record is None) == self.user_awake
