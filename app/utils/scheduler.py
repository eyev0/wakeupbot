from datetime import datetime
from typing import Optional

import pendulum
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
from app.filters.sleep_tracker import UserAwakeFilter
from app.middlewares.i18n import i18n
from app.misc import bot
from app.models.reminder import BedtimeReminder, WakeupReminder
from app.models.user import User
from app.utils.sleep_tracker import get_sleep_markup
from app.utils.time import SLEEP_HOURS, SLEEP_MINUTES, parse_time, parse_tz

_ = i18n.gettext
scheduler = AsyncIOScheduler()
JOBSTORE_DEFAULT = "default"


async def delete_bedtime_reminder(user: User):
    logger.info(f"Removing bedtime reminder for user {user.id}")
    reminder: BedtimeReminder = await BedtimeReminder.query.where(
        BedtimeReminder.user_id == user.id
    ).gino.first()
    if reminder:
        scheduler.remove_job(reminder.job_id, JOBSTORE_DEFAULT)
        await reminder.delete()


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
    logger.info(f"Time: {time.to_time_string()}, tz: {tz.name}")
    time = time.set(tz=tz).in_tz(scheduler.timezone)

    reminder: BedtimeReminder = await BedtimeReminder.query.where(
        BedtimeReminder.user_id == user.id
    ).gino.first()
    trigger = CronTrigger(hour=time.hour, minute=time.minute)
    if reminder:
        scheduler.reschedule_job(reminder.job_id, JOBSTORE_DEFAULT, trigger)
    else:
        job = scheduler.add_job(
            execute_job_func, trigger, args=(bedtime_reminder_func, user)
        )
        await BedtimeReminder.create(job_id=job.id, user_id=user.id)


async def schedule_wakeup_reminder(user: User):
    logger.info(f"Scheduling wakeup reminder for user {user.id}")
    tz: FixedTimezone = parse_tz(user.timezone)
    time: DateTime = pendulum.now(tz)
    logger.info(f"Time: {time.to_time_string()}, tz: {tz.name}")
    time = time.in_tz(scheduler.timezone)

    reminder: WakeupReminder = await WakeupReminder.query.where(
        WakeupReminder.user_id == user.id
    ).gino.first()
    trigger = CronTrigger(
        hour=(time.hour + SLEEP_HOURS) % 24,
        minute=(time.minute + SLEEP_MINUTES) % 60,
        end_date=datetime.fromtimestamp(
            time.add(hours=SLEEP_HOURS, minutes=(SLEEP_MINUTES + 5) % 60).timestamp()
        ),
    )
    if reminder:
        scheduler.reschedule_job(
            reminder.job_id, JOBSTORE_DEFAULT, trigger,
        )
    else:
        job = scheduler.add_job(
            execute_job_func, trigger, args=(wakeup_reminder_func, user)
        )
        await WakeupReminder.create(job_id=job.id, user_id=user.id)


async def execute_job_func(func, *args):
    return await func(*args)


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


async def wakeup_reminder_func(user: User):
    if await UserAwakeFilter(user_awake=False).check():
        logger.info(f"Sending wakeup reminder to user {user.id}")
        await bot.send_message(
            user.id, hitalic(_("Did you wake up?")), disable_notification=True,
        )


async def update_jobs_callables(s: AsyncIOScheduler, jobstore):
    logger.info("Migrationg jobs for scheduler")
    for reminder in await BedtimeReminder.query.gino.all():
        user: User = await User.get(reminder.user_id)
        s.modify_job(
            reminder.job_id,
            jobstore,
            func=execute_job_func,
            args=(bedtime_reminder_func, user),
        )
    for reminder in await WakeupReminder.query.gino.all():
        user: User = await User.get(reminder.user_id)
        s.modify_job(
            reminder.job_id,
            jobstore,
            func=execute_job_func,
            args=(wakeup_reminder_func, user),
        )


async def on_startup(dispatcher: Dispatcher):
    logger.info("Configuring scheduler..")
    jobstores = {JOBSTORE_DEFAULT: SQLAlchemyJobStore(url=config.POSTGRES_URI)}
    job_defaults = {"misfire_grace_time": 300}
    scheduler.configure(
        jobstores=jobstores, job_defaults=job_defaults,
    )
    scheduler.start(paused=True)
    await update_jobs_callables(scheduler, JOBSTORE_DEFAULT)
    scheduler.resume()


async def on_shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down scheduler..")
    scheduler.shutdown()


def setup(executor: Executor):
    executor.on_startup(on_startup)
    executor.on_shutdown(on_shutdown)
