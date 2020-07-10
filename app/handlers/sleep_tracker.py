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
from app.utils.sleep_tracker import explicit_stats, stats_by_day

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
    record: SleepRecord = await SleepRecord.query.where(
        and_(SleepRecord.user_id == user.id, SleepRecord.check_wakeup == False)  # noqa
    ).gino.first()
    record_id = record.id
    await record.update(check_wakeup=True).apply()
    record: SleepRecord = await SleepRecord.get(record_id)

    interval = Period(record.created_at, record.updated_at).as_interval()
    dt_created_at = pendulum.instance(record.created_at)
    dt_updated_at = pendulum.instance(record.updated_at)

    text = [
        hbold(_("Good morning!")),
        _("Your sleep:"),
        f"{datetime_fmtr.format(dt_created_at, 'D MMMM, dd HH:mm:ss', chat.language)}"
        + " - "
        + f"{datetime_fmtr.format(dt_updated_at, 'D MMMM, dd HH:mm:ss', chat.language)}"
        + " -- "
        + hbold(
            _("{hours}h {minutes}min").format(
                hours=interval.hours, minutes=interval.minutes,
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
    now = pendulum.now()
    command, *args = message.text.split(maxsplit=1)
    args = args[-1] if args else ""
    if args:
        try:
            month_diff = int(args)
        except ValueError:
            await message.answer(_("Wrong option! '{option}'".format(option=args)))
            return
        month = (now.month + month_diff - 12) % 12
        if month == 0:
            month = 12
        year = now.year + int((now.month + month_diff - 12) / 12)
    else:
        month = now.month
        year = now.year
    month_dt = DateTime(year=year, month=month, day=1)
    start = now.replace(
        year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end = now.replace(
        year=year,
        month=month,
        day=month_dt.days_in_month,
        hour=23,
        minute=59,
        second=59,
        microsecond=0,
    )

    sleep_records = (
        await SleepRecord.query.where(
            and_(
                SleepRecord.user_id == user.id,
                SleepRecord.created_at >= start,
                SleepRecord.created_at <= end,
            )
        )
        .order_by(SleepRecord.created_at)
        .gino.all()
    )

    explicit = [x for x in explicit_stats(sleep_records, chat.language)]
    by_day = [x for x in stats_by_day(sleep_records, chat.language)]
    avg_sleep_per_day = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), by_day)) / max(len(by_day), 1)
    )

    text = [
        hbold(
            _("Monthly stats for {month_year}: ").format(
                month_year=datetime_fmtr.format(month_dt, "MMMM YYYY", chat.language)
            )
        ),
        "",
        *explicit,
        "",
        hbold(_("Average sleep hours per day:")),
        hbold(
            _("{hours}h {minutes}min").format(
                hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
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
    sleep_records = (
        await SleepRecord.query.where(
            and_(SleepRecord.user_id == user.id, SleepRecord.created_at > monday_0am)
        )
        .order_by(SleepRecord.created_at)
        .gino.all()
    )

    explicit = [x for x in explicit_stats(sleep_records, chat.language)]
    by_day = [x for x in stats_by_day(sleep_records, chat.language)]
    avg_sleep_per_day = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), by_day)) / max(len(by_day), 1)
    )

    text = [
        hbold(_("Weekly stats: ")),
        "",
        *explicit,
        "",
        hbold(_("Average sleep hours per day:")),
        hbold(
            _("{hours}h {minutes}min").format(
                hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
            )
        ),
    ]
    await message.answer("\n".join(text))
