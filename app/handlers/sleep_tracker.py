import pendulum
from aiogram import types
from aiogram.utils.markdown import hbold, hitalic
from loguru import logger
from pendulum import Duration, Period
from sqlalchemy import and_

from app.middlewares.i18n import i18n
from app.misc import dp
from app.models.chat import Chat
from app.models.sleep_record import SleepRecord
from app.models.user import User
from app.utils.sleep_tracker import (
    as_datetime,
    as_month,
    as_short_date,
    get_explicit_stats,
    get_stats_by_day,
    parse_timezone,
    subtract_from,
)

_ = i18n.gettext


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

    tz = parse_timezone(user.timezone)
    interval = Period(record.created_at, record.updated_at).as_interval()
    dt_created_at = pendulum.instance(record.created_at)
    dt_updated_at = pendulum.instance(record.updated_at)

    text = [
        hbold(_("Good morning!")),
        _("Your sleep:"),
        f"{as_datetime(dt_created_at, tz, chat.language)}"
        + " - "
        + f"{as_datetime(dt_updated_at, tz, chat.language)}"
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
    tz = parse_timezone(user.timezone)
    now = pendulum.now(tz)
    try:
        dt = subtract_from(date=now, diff=message.text, period="month")
    except ValueError:
        await message.answer(_("Wrong option! - {option}").format(option=message.text))
        return
    start = pendulum.instance(
        now.replace(
            year=dt.year,
            month=dt.month,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    )
    end = start.add(months=1)

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

    explicit_stats = [x for x in get_explicit_stats(sleep_records, tz, chat.language)]
    grouped_by_day = [
        x
        for x in get_stats_by_day(
            sleep_records, tz, chat.language, mode="month", days=start.days_in_month
        )
    ]
    avg_sleep_per_day = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), grouped_by_day))
        / max(len(grouped_by_day), 1)
    )

    text = [
        hbold(
            _("Monthly stats for {month_year}: ").format(
                month_year=as_month(dt, tz, chat.language)
            )
        ),
        "",
        *explicit_stats,
        "",
        hbold(_("Average sleep hours per day:")),
        hbold(
            _("{hours}h {minutes}min").format(
                hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
            )
        ),
    ]
    await message.answer("\n".join(text))


@dp.message_handler(text_startswith="!")
async def sleep_statistics_week(message: types.Message, user: User, chat: Chat):
    logger.info(
        "User {user} requested weekly sleep statistics", user=message.from_user.id
    )
    tz = parse_timezone(user.timezone)
    now = pendulum.now(tz)
    try:
        dt = subtract_from(date=now, diff=message.text, period="week")
    except ValueError:
        await message.answer(_("Wrong option! - {option}").format(option=message.text))
        return
    start = pendulum.instance(
        dt.subtract(days=dt.weekday()).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
    )
    end = start.add(weeks=1)

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

    explicit_stats = [x for x in get_explicit_stats(sleep_records, tz, chat.language)]
    grouped_by_day = [x for x in get_stats_by_day(sleep_records, tz, chat.language)]
    avg_sleep_per_day = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), grouped_by_day))
        / max(len(grouped_by_day), 1)
    )

    text = [
        hbold(
            _("Weekly stats ({start} - {end}): ").format(
                start=as_short_date(start, tz, chat.language),
                end=as_short_date(end, tz, chat.language),
            )
        ),
        "",
        *explicit_stats,
        "",
        hbold(_("Average sleep hours per day:")),
        hbold(
            _("{hours}h {minutes}min").format(
                hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
            )
        ),
    ]
    await message.answer("\n".join(text))
