from typing import Optional

from aiogram.utils.markdown import hitalic
from loguru import logger
from pendulum import DateTime
from pendulum.tz.timezone import FixedTimezone

from app.filters.sleep_tracker import UserAwakeFilter
from app.middlewares.i18n import i18n
from app.misc import bot
from app.models.reminders import BedtimeReminder
from app.models.user import User
from app.utils.datetime import parse_time, parse_tz
from app.utils.sleep_tracker import get_sleep_markup

_ = i18n.gettext


async def delete_bedtime_reminder(user: User):
    logger.info(f"Removing bedtime reminder for user {user.id}")
    reminder: BedtimeReminder = await BedtimeReminder.query.where(
        BedtimeReminder.user_id == user.id
    ).gino.first()
    if reminder:
        from app.utils.scheduler import (
            JOBSTORE_DEFAULT,
            scheduler,
        )

        scheduler.remove_job(reminder.job_id, JOBSTORE_DEFAULT)
        await BedtimeReminder.delete.where(
            BedtimeReminder.job_id == reminder.job_id
        ).apply()


async def schedule_bedtime_reminder(
    user: User, time: Optional[DateTime] = None, tz: Optional[FixedTimezone] = None,
):
    logger.info(f"Rescheduling bedtime reminder for user {user.id}")
    if not tz:
        tz: FixedTimezone = parse_tz(user.timezone)
    if not time:
        if user.reminder == "-":
            # no reminder set for user, no need to reschedule job
            return
        time: DateTime = parse_time(user.reminder)
        time = time.set(tz=tz)
    logger.info(f"Time: {time.to_time_string()}, tz: {tz.name}")

    reminder: BedtimeReminder = await BedtimeReminder.query.where(
        BedtimeReminder.user_id == user.id
    ).gino.first()
    job_id = reminder.job_id if reminder else None

    from app.utils.scheduler import scheduler, schedule_job

    time = time.in_tz(scheduler.timezone)
    await schedule_job(job_id, BedtimeReminder, time, bedtime_reminder_func, user)


async def bedtime_reminder_func(user: User):
    logger.info(f"Sending bedtime reminder to user {user.id}")
    if await UserAwakeFilter(user_awake=True).check():
        markup = get_sleep_markup(_("I'm going to sleep"), "sleep")
        await bot.send_message(
            user.id,
            hitalic(_("Hey!.. Time to sleep, my dear friend.")),
            disable_notification=user.do_not_disturb,
            reply_markup=markup,
        )
