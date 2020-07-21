from typing import List, Union

import pendulum
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.markdown import hbold
from loguru import logger
from pendulum import DateTime, Duration, Period
from pendulum.tz.timezone import FixedTimezone

from app.middlewares.i18n import i18n
from app.models.sleep_record import SleepRecord

_ = i18n.gettext
datetime_fmtr = pendulum.Formatter()
latenight_offset = Duration(hours=5)
cb_moods = CallbackData("user", "record_id", "mood", "emoji")


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


def parse_timezone(timezone: str) -> Union[FixedTimezone, None]:
    try:
        sign = timezone[0]
        if sign not in ["-", "+"]:
            raise ValueError
        offset = duration_from_timezone(timezone)
        return pendulum.tz.fixed_timezone(int(sign + "1") * offset.in_seconds())
    except ValueError as e:
        logger.info(f"Wrong timezone format: {timezone}")
        raise e


def duration_from_timezone(timezone: Union[FixedTimezone, str]) -> Duration:
    if isinstance(timezone, FixedTimezone):
        timezone = timezone.name
    hours, *minutes = timezone[1:].split(":", maxsplit=1)
    minutes = minutes[-1] if minutes else "0"
    duration = pendulum.Duration(hours=int(hours), minutes=int(minutes))
    return duration


def as_short_date(dt: DateTime, tz, locale):
    return datetime_fmtr.format(dt.in_tz(tz), "D MMM", locale)


def as_month(dt: DateTime, tz, locale):
    return datetime_fmtr.format(dt.in_tz(tz), "MMMM YYYY", locale)


def as_datetime(dt: DateTime, tz, locale):
    return datetime_fmtr.format(dt.in_tz(tz), "D MMMM, dd HH:mm:ss", locale)


def as_time(dt: DateTime, tz):
    return datetime_fmtr.format(dt.in_tz(tz), "HH:mm:ss")


def as_weekday(dt: DateTime, tz, locale):
    return datetime_fmtr.format(dt.in_tz(tz), "dd", locale)


def as_weekday_int(dt: DateTime, tz):
    return datetime_fmtr.format(dt.in_tz(tz), "d")


def as_day(dt: DateTime, tz):
    return datetime_fmtr.format(dt.in_tz(tz), "D")
