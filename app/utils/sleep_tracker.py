from typing import List

import pendulum
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.markdown import hbold
from loguru import logger
from pendulum import DateTime, Duration, Period

from app.middlewares.i18n import i18n
from app.models.sleep_record import SleepRecord
from app.utils.time import (
    as_day,
    as_short_date,
    as_time,
    as_weekday,
    as_weekday_int,
    latenight_offset,
)

_ = i18n.gettext
cb_moods = CallbackData("user", "record_id", "mood", "emoji")
cb_sleep = CallbackData("user", "action")


def get_moods_markup(record_id) -> InlineKeyboardMarkup:
    mood_ok = (_("Ok"), "🙂")
    mood_well_slept = (_("Well slept"), "😃️")
    mood_sluggish = (_("Sluggish"), "😪")
    mood_sleepy = (_("Sleepy"), "😴")
    moods_rows = [
        [mood_ok, mood_well_slept],
        [mood_sluggish, mood_sleepy],
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_(mood + emoji),
                    callback_data=cb_moods.new(
                        record_id=record_id, mood=mood, emoji=emoji
                    ),
                )
                for mood, emoji in moods
            ]
            for moods in moods_rows
        ]
    )


def get_sleep_markup(text: str, action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text, callback_data=cb_sleep.new(action=action),
                )
            ]
        ]
    )


def subtract_from(date: DateTime, diff: str, period: str) -> DateTime:
    new_dt = date
    command, *args = diff.split(maxsplit=1)
    args = args[-1] if args else ""
    if args:
        try:
            diff = -int(args)
        except ValueError as e:
            logger.error(e)
            raise e
        if period == "month":
            new_dt = date.subtract(months=diff)
        elif period == "week":
            new_dt = date.subtract(weeks=diff)
    return new_dt


def get_records_stats(records: List[SleepRecord], tz, language):
    result = []
    for record in records:
        dt_start = pendulum.instance(record.created_at)
        dt_start_fixed_weekday = dt_start.subtract(
            seconds=latenight_offset.in_seconds()
        )
        dt_end = pendulum.instance(record.wakeup_time)
        interval = Period(dt_start, dt_end).as_interval()
        result.append(
            f"{as_weekday(dt_start_fixed_weekday, tz, language)}, "
            + f"{as_short_date(dt_start_fixed_weekday, tz, language)} "
            + f"{as_time(dt_start, tz)}"
            + " - "
            + f"{as_time(dt_end, tz)}"
            + " -- "
            + hbold(
                _("{hours}h {minutes}min").format(
                    hours=interval.hours, minutes=interval.minutes,
                )
            )
            + (f"({record.emoji})" if record.emoji else "")
        )
    return result


def get_stats_grouped_by_day(
    records: List[SleepRecord], tz, language, mode="week", days=7
):
    if mode == "week":
        get_day_func = as_weekday_int
    elif mode == "month":
        days = days + 1
        get_day_func = as_day
    else:
        return []
    tmp_res = [Duration() for i in range(days)]
    result = []
    for record in records:
        dt_start = pendulum.instance(record.created_at)
        dt_start_fixed_weekday = dt_start.subtract(
            seconds=latenight_offset.in_seconds()
        )
        dt_end = pendulum.instance(record.wakeup_time)
        interval = Period(dt_start, dt_end).as_interval()
        i = int(get_day_func(dt_start_fixed_weekday, tz))
        tmp_res[i] = tmp_res[i] + interval
    for x in filter(lambda a: a.in_seconds() > 0, tmp_res):
        result.append(x)
    return result


def get_average_sleep(records: List[SleepRecord], tz, language, mode="week", days=7):
    grouped_by_day = get_stats_grouped_by_day(
        records, tz, language, mode=mode, days=days
    )
    avg_sleep_per_day = Duration(
        seconds=sum(map(lambda x: x.in_seconds(), grouped_by_day))
        / max(len(grouped_by_day), 1)
    )
    return avg_sleep_per_day
