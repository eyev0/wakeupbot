from typing import Union

import pendulum
from aiogram import Dispatcher
from aiogram.utils.executor import Executor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app import config
from app.models.reminders import BedtimeReminder, WakeupReminder
from app.models.user import User
from app.utils.bedtime_reminder import bedtime_reminder_func
from app.utils.wakeup_reminder import wakeup_reminder_func

scheduler = AsyncIOScheduler()
JOBSTORE_DEFAULT = "default"


async def execute_job_func(func, *args):
    return await func(*args)


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


async def schedule_job(
    job_id: Union[str, None],
    reminder_cls: Union[type(BedtimeReminder), type(WakeupReminder)],
    time,
    func,
    user,
):
    trigger = CronTrigger(hour=time.hour, minute=time.minute,)
    if job_id:
        scheduler.reschedule_job(
            job_id, JOBSTORE_DEFAULT, trigger,
        )
        await reminder_cls.update.values(updated_at=pendulum.now()).where(
            reminder_cls.job_id == job_id
        ).gino.status()
    else:
        job = scheduler.add_job(execute_job_func, trigger, args=(func, user))
        await reminder_cls.create(job_id=job.id, user_id=user.id)
