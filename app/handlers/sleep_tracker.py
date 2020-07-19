import pendulum
from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.markdown import hbold, hitalic
from loguru import logger
from pendulum import Period
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
    cb_moods,
    get_average_sleep,
    get_moods_markup,
    get_records_stats,
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
    await message.answer(
        _("How do you feel?"), reply_markup=get_moods_markup(record.id)
    )


@dp.callback_query_handler(cb_moods.filter())
async def cq_user_wakeup_mood(
    query: types.CallbackQuery, user: User, callback_data: dict
):
    logger.info(
        "User {user} logged his mood", user=query.from_user.id,
    )
    mood = callback_data["mood"]
    emoji = callback_data["emoji"]
    mood_text = mood + emoji
    sleep_record: SleepRecord = await SleepRecord.get(int(callback_data["record_id"]))
    await sleep_record.update(mood=mood, emoji=emoji).apply()

    text = [_("Mood this morning"), mood_text]
    await query.answer()
    await query.message.edit_text(
        text="\n".join(text), reply_markup=InlineKeyboardMarkup()
    )


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

    monthly_records = []
    start_dt = pendulum.instance(
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
    text = [
        hbold(
            _("Monthly stats for {month_year}: ").format(
                month_year=as_month(dt, tz, chat.language)
            )
        ),
    ]

    end_dt = start_dt.add(weeks=1)
    if end_dt.day_of_week != 0:
        end_dt = end_dt.subtract(days=end_dt.day_of_week - 1)

    break_ = False
    while not break_:
        if end_dt.month != start_dt.month:
            end_dt = end_dt.subtract(days=end_dt.day)
            break_ = True
        weekly_records = (
            await SleepRecord.query.where(
                and_(
                    SleepRecord.user_id == user.id,
                    SleepRecord.created_at >= start_dt,
                    SleepRecord.created_at <= end_dt,
                )
            )
            .order_by(SleepRecord.created_at)
            .gino.all()
        )
        if weekly_records:
            monthly_records.extend(weekly_records)
            explicit_stats = get_records_stats(weekly_records, tz, chat.language)
            avg_sleep_per_day = get_average_sleep(weekly_records, tz, chat.language)
            text.extend(
                [
                    "",
                    hbold(
                        _("{start} - {end}: ").format(
                            start=as_short_date(start_dt, tz, chat.language),
                            end=as_short_date(end_dt, tz, chat.language),
                        )
                    ),
                    *explicit_stats,
                    hbold(_("Average sleep:")),
                    hbold(
                        _("{hours}h {minutes}min").format(
                            hours=avg_sleep_per_day.hours,
                            minutes=avg_sleep_per_day.minutes,
                        )
                    ),
                ]
            )
        if break_:
            break
        end_dt = end_dt.add(weeks=1)
        start_dt = end_dt.subtract(weeks=1)

    avg_sleep_per_day = get_average_sleep(
        monthly_records, tz, chat.language, mode="month", days=start_dt.days_in_month
    )

    text.extend(
        [
            "",
            hbold(_("Monthly average sleep:")),
            hbold(
                _("{hours}h {minutes}min").format(
                    hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
                )
            ),
        ]
    )
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
    start_dt = pendulum.instance(
        dt.subtract(days=dt.weekday()).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
    )
    end_dt = start_dt.add(weeks=1)

    weekly_records = (
        await SleepRecord.query.where(
            and_(
                SleepRecord.user_id == user.id,
                SleepRecord.created_at >= start_dt,
                SleepRecord.created_at <= end_dt,
            )
        )
        .order_by(SleepRecord.created_at)
        .gino.all()
    )

    explicit_stats = get_records_stats(weekly_records, tz, chat.language)
    avg_sleep_per_day = get_average_sleep(weekly_records, tz, chat.language)

    text = [
        hbold(
            _("Weekly stats ({start} - {end}): ").format(
                start=as_short_date(start_dt, tz, chat.language),
                end=as_short_date(end_dt, tz, chat.language),
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
