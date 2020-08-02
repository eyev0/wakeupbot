from typing import Optional

from aiogram import Dispatcher
from aiogram.utils.executor import Executor
from aiogram.utils.markdown import hitalic
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from pendulum import DateTime
from pendulum.tz.timezone import FixedTimezone

from app import config
from app.middlewares.i18n import i18n
from app.misc import bot
from app.models.reminder import ReminderJob
from app.models.user import User
from app.utils.sleep_tracker import get_sleep_markup
from app.utils.time import parse_time, parse_tz

_ = i18n.gettext
scheduler = AsyncIOScheduler()


async def reschedule_user_reminder_job(
    user: User, time: Optional[DateTime] = None, tz: Optional[FixedTimezone] = None,
):
    logger.info(f"Rescheduling bedtime reminder for user {user.id}")
    if not tz:
        tz: FixedTimezone = parse_tz(user.timezone)
    if not time:
        time: DateTime = parse_time(user.reminder)
    logger.info(f"Time: {time.to_time_string()}, tz: {tz.name}")

    reminder_job: ReminderJob = await ReminderJob.query.where(
        ReminderJob.user_id == user.id
    ).gino.first()
    if reminder_job:
        scheduler.remove_job(reminder_job.job_id, jobstore="default")
    # set time's tz to user's value
    time = time.set(tz=tz)
    # convert time to scheduler's tz
    time = time.in_tz(scheduler.timezone)

    scheduler_job = scheduler.add_job(
        bedtime_reminder, CronTrigger(hour=time.hour, minute=time.minute), args=(user,)
    )
    reminder_job = await ReminderJob.create(job_id=scheduler_job.id, user_id=user.id)


async def bedtime_reminder(user: User):
    logger.info(f"Sending bedtime reminder to user {user.id}")
    markup = get_sleep_markup(_("I'm going to sleep"), "sleep")
    await bot.send_message(
        user.id,
        hitalic(_("Hey!.. Time to sleep, my dear friend.")),
        disable_notification=user.do_not_disturb,
        reply_markup=markup,
    )


async def on_startup(dispatcher: Dispatcher):
    logger.info("Configuring scheduler..")

    jobstores = {"default": SQLAlchemyJobStore(url=config.POSTGRES_URI)}
    job_defaults = {"misfire_grace_time": 300}
    scheduler.configure(
        jobstores=jobstores, job_defaults=job_defaults,
    )

    scheduler.start()


async def on_shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down scheduler..")

    scheduler.shutdown()


def setup(executor: Executor):
    executor.on_startup(on_startup)
    executor.on_shutdown(on_shutdown)
