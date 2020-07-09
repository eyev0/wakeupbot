import pendulum
from aiogram import types
from aiogram.utils.markdown import hbold, hitalic
from loguru import logger
from pendulum import DateTime, Duration, Period
from sqlalchemy import and_

from app.middlewares.i18n import i18n
from app.misc import dp
from app.models.chat import Chat
from app.models.sleep_record import SleepRecord
from app.models.user import User

_ = i18n.gettext
datetime_fmtr = pendulum.Formatter()


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

    start_timedate = rec.created_at
    end_timedate = rec.updated_at
    sleep_time = Period(start_timedate, end_timedate)

    text = [
        hbold(_("Good morning!")),
        _("Your sleep started ")
        + hbold(
            f"{datetime_fmtr.format(start_timedate, 'D MMMM, HH:mm:ss', chat.language)}"
        ),
        _("Ended ")
        + hbold(
            f"{datetime_fmtr.format(end_timedate, 'D MMMM, HH:mm:ss', chat.language)}"
        ),
        _("Sleep time: ")
        + hbold(
            _("{hours}h {minutes}m {seconds}s").format(
                hours=sleep_time.hours,
                minutes=sleep_time.minutes,
                seconds=sleep_time.seconds,
            )
        ),
    ]
    await message.answer("\n".join(text))


@dp.message_handler(text_startswith="!м")
@dp.message_handler(text_startswith="!m")
async def sleep_statistics_month(message: types.Message, user: User, chat: Chat):
    logger.info(
        "User {user} requested monthly sleep statistics, command - {cmd}",
        user=message.from_user.id,
        cmd=message.text,
    )

    command, *args = message.text.split(maxsplit=1)
    args = args[-1] if args else ""
    if args:
        try:
            month_diff = int(args)
        except ValueError:
            await message.answer(_("Wrong option! - {option}".format(option=args)))
            return
    else:
        month_diff = 0

    now = pendulum.now()
    date = DateTime(year=now.year, month=now.month + month_diff, day=1)

    start = now.replace(
        month=date.month, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end = now.replace(
        month=date.month,
        day=date.days_in_month,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    sleep_records = await SleepRecord.query.where(
        and_(SleepRecord.created_at >= start, SleepRecord.created_at <= end)
    ).gino.all()

    stats = []
    intervals = []
    for record in sleep_records:
        day_of_month = datetime_fmtr.format(record.updated_at, "D MMMM", chat.language)
        interval = Period(record.created_at, record.updated_at).as_interval()
        intervals.append(interval)
        stats.append(
            f"{day_of_month} - "
            + f"{datetime_fmtr.format(record.created_at, 'HH:mm:ss', chat.language)}"
            + "-"
            + f"{datetime_fmtr.format(record.updated_at, 'HH:mm:ss', chat.language)}"
            + " - "
            + hbold(
                _("{hours}h {minutes}m {seconds}s").format(
                    hours=interval.hours,
                    minutes=interval.minutes,
                    seconds=interval.seconds,
                )
            )
        )

    avg_sleep = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), intervals)) / max(len(intervals), 1)
    )
    text = [
        hbold(
            _("Monthly stats for {month}: ").format(
                month=datetime_fmtr.format(date, "MMMM", chat.language)
            )
        ),
        "",
        *stats,
        "",
        hbold(_("Average sleep hours:")),
        hbold(
            _("{hours}h {minutes}m {seconds}s").format(
                hours=avg_sleep.hours,
                minutes=avg_sleep.minutes,
                seconds=avg_sleep.seconds,
            )
        ),
    ]
    await message.answer("\n".join(text))


@dp.message_handler(text="!")
async def sleep_statistics_week(message: types.Message, user: User, chat: Chat):
    logger.info(
        "User {user} requested weekly sleep statistics", user=message.from_user.id
    )
    now = pendulum.now()
    monday_0am = now.replace(
        day=now.day - now.weekday(), hour=0, minute=0, second=0, microsecond=0
    )
    sleep_records = await SleepRecord.query.where(
        SleepRecord.created_at > monday_0am
    ).gino.all()

    stats = []
    intervals = []
    for record in sleep_records:
        day_of_month = datetime_fmtr.format(record.updated_at, "D MMMM", chat.language)
        interval = Period(record.created_at, record.updated_at).as_interval()
        intervals.append(interval)
        stats.append(
            f"{day_of_month} - "
            + f"{datetime_fmtr.format(record.created_at, 'HH:mm:ss', chat.language)}"
            + "-"
            + f"{datetime_fmtr.format(record.updated_at, 'HH:mm:ss', chat.language)}"
            + " - "
            + hbold(
                _("{hours}h {minutes}m {seconds}s").format(
                    hours=interval.hours,
                    minutes=interval.minutes,
                    seconds=interval.seconds,
                )
            )
        )

    avg_sleep = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), intervals)) / len(intervals)
    )
    text = [
        hbold(_("Weekly stats: ")),
        "",
        *stats,
        "",
        hbold(_("Average sleep hours:")),
        hbold(
            _("{hours}h {minutes}m {seconds}s").format(
                hours=avg_sleep.hours,
                minutes=avg_sleep.minutes,
                seconds=avg_sleep.seconds,
            )
        ),
    ]
    await message.answer("\n".join(text))
