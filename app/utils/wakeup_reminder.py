from aiogram.utils.markdown import hitalic
from loguru import logger
from pendulum import DateTime, Duration
from pendulum.tz.timezone import FixedTimezone

from app.filters.sleep_tracker import UserAwakeFilter
from app.middlewares.i18n import i18n
from app.misc import bot
from app.models.reminders import WakeupReminder
from app.models.user import User

SLEEP_HOURS = 6
SLEEP_MINUTES = 30
SLEEP_SECONDS = 0
sleep_duration = Duration(
    hours=SLEEP_HOURS, minutes=SLEEP_MINUTES, seconds=SLEEP_SECONDS
)
_ = i18n.gettext


async def schedule_wakeup_reminder(
    user: User, time: DateTime, tz: FixedTimezone,
):
    logger.info(f"Scheduling wakeup reminder for user {user.id}")
    logger.info(f"Time: {time.to_time_string()}, tz: {tz.name}")

    reminder: WakeupReminder = await WakeupReminder.query.where(
        WakeupReminder.user_id == user.id
    ).gino.first()
    job_id = reminder.job_id if reminder else None

    from app.utils.scheduler import scheduler, schedule_job

    time = time.in_tz(scheduler.timezone)
    await schedule_job(job_id, WakeupReminder, time, wakeup_reminder_func, user)


async def wakeup_reminder_func(user: User):
    if await UserAwakeFilter(user_awake=False, user=user).check():
        logger.info(f"Sending wakeup reminder to user {user.id}")
        await bot.send_message(
            user.id, hitalic(_("Did you wake up?")), disable_notification=True,
        )
