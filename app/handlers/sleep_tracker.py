import asyncio
from contextlib import suppress

import pendulum
from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.exceptions import MessageCantBeDeleted
from aiogram.utils.markdown import hbold, hitalic
from loguru import logger
from pendulum import Period
from sqlalchemy import and_

from app.filters.sleep_tracker import UserAwakeFilter
from app.middlewares.i18n import i18n
from app.misc import dp
from app.models.chat import Chat
from app.models.sleep_record import SleepRecord
from app.models.user import User
from app.utils.scheduler import schedule_wakeup_reminder
from app.utils.sleep_tracker import (
    cb_moods,
    cb_sleep_or_wakeup,
    get_average_sleep,
    get_moods_markup,
    get_records_stats,
    get_sleep_markup,
    subtract_from,
)
from app.utils.time import (
    VISUAL_GRACE_TIME,
    as_datetime,
    as_month,
    as_short_date,
    latenight_offset,
    parse_tz,
)

_ = i18n.gettext


@dp.message_handler(text="-", user_awake=True)
async def sleep_start(message: types.Message, user: User):
    logger.info("User {user} is going to sleep now", user=user.id)
    await SleepRecord.create(user_id=user.id)
    await schedule_wakeup_reminder(user)
    markup = get_sleep_markup(_("I woke up"), "wakeup")
    await asyncio.sleep(VISUAL_GRACE_TIME)
    await message.answer(hitalic(_("Good night..")), reply_markup=markup)


@dp.message_handler(text="+", user_awake=False)
async def sleep_end(message: types.Message, user: User, chat: Chat):
    logger.info("User {user} is waking up now", user=user.id)
    now = pendulum.now()
    record: SleepRecord = await SleepRecord.query.where(
        and_(SleepRecord.user_id == user.id, SleepRecord.wakeup_time == None)  # noqa
    ).gino.first()
    tz = parse_tz(user.timezone)
    interval = Period(record.created_at, now).as_interval()
    text = [
        hbold(_("Good morning!")),
        _("Your sleep:"),
        f"{as_datetime(pendulum.instance(record.created_at), tz, chat.language)}"
        + " - "
        + f"{as_datetime(now, tz, chat.language)}"
        + " -- "
        + hbold(
            _("{hours}h {minutes}min").format(
                hours=interval.hours, minutes=interval.minutes,
            )
        ),
    ]
    await record.update(wakeup_time=now).apply()
    await asyncio.sleep(VISUAL_GRACE_TIME)
    await message.answer("\n".join(text))
    await asyncio.sleep(VISUAL_GRACE_TIME)
    await message.answer(
        _("How do you feel?"), reply_markup=get_moods_markup(record.id)
    )


@dp.callback_query_handler(cb_sleep_or_wakeup.filter())
async def cq_user_sleep_or_wakeup(
    query: types.CallbackQuery, user: User, chat: Chat, callback_data: dict
):

    logger.info(
        "User {user} pressed {action} button",
        user=query.from_user.id,
        action=(action := callback_data["action"]),
    )
    await query.answer()
    if action == "sleep" and await UserAwakeFilter(user_awake=True).check():
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await query.message.delete()
        await sleep_start(query.message, user)
    elif action == "wakeup" and await UserAwakeFilter(user_awake=False).check():
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await query.message.delete()
        await sleep_end(query.message, user, chat)
    else:
        return


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
    tz = parse_tz(user.timezone)
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
    ).add(seconds=latenight_offset.in_seconds())
    text = [
        hbold(
            _("Monthly stats for {month_year}: ").format(
                month_year=as_month(dt, tz, chat.language)
            )
        ),
    ]

    end_dt = start_dt.add(weeks=1)
    end_dt = end_dt.subtract(days=max(end_dt.day_of_week - 1, 0))

    break_ = False
    while not break_:
        if end_dt.month != start_dt.month:
            end_dt = end_dt.subtract(days=end_dt.day - 1)
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
                        "{start} - {end}: ".format(
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
        start_dt = end_dt
        end_dt = end_dt.add(weeks=1)

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
    tz = parse_tz(user.timezone)
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
    ).add(seconds=latenight_offset.in_seconds())
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
        hbold(_("Average sleep:")),
        hbold(
            _("{hours}h {minutes}min").format(
                hours=avg_sleep_per_day.hours, minutes=avg_sleep_per_day.minutes,
            )
        ),
    ]
    await message.answer("\n".join(text))
