import pendulum
from aiogram import types
from aiogram.utils.markdown import hbold, hitalic
from loguru import logger
from pendulum import Period
from sqlalchemy import and_

from app.middlewares.i18n import i18n
from app.misc import dp
from app.models.chat import Chat
from app.models.sleep_record import SleepRecord
from app.models.user import User

_ = i18n.gettext


@dp.message_handler(text="-", user_awake=True)
async def sleep_start(message: types.Message, user: User):
    logger.info("User {user} is going to sleep now", user=message.from_user.id)
    await SleepRecord.create(user_id=user.id)
    await message.answer(hitalic(_("Good night..")))


@dp.message_handler(text="+", user_awake=False)
async def sleep_end(message: types.Message, user: User, chat: Chat):
    logger.info("User {user} is waking up now", user=message.from_user.id)
    rec: SleepRecord = await SleepRecord.query.where(
        and_(SleepRecord.user_id == user.id, SleepRecord.check_wakeup == False)  # noqa
    ).gino.first()
    record_id = rec.id
    await rec.update(check_wakeup=True).apply()
    rec: SleepRecord = await SleepRecord.get(record_id)

    fmtr = pendulum.Formatter()
    start_timedate = rec.created_at
    end_timedate = rec.updated_at
    sleep_time = Period(start_timedate, end_timedate)

    text = [
        hbold(_("Good morning!")),
        _("Your sleep started ")
        + hbold(f"{fmtr.format(start_timedate, 'D MMMM, HH:mm:ss', chat.language)}"),
        _("Ended ")
        + hbold(f"{fmtr.format(end_timedate, 'D MMMM, HH:mm:ss', chat.language)}"),
        _("Sleep time: ")
        + hbold(
            _("{hours} hours {minutes} minutes {seconds} seconds").format(
                hours=sleep_time.hours,
                minutes=sleep_time.minutes,
                seconds=sleep_time.seconds,
            )
        ),
    ]
    await message.answer("\n".join(text))
