from typing import List, Union

import pendulum
from aiogram.utils.markdown import hbold
from loguru import logger
from pendulum import DateTime, Duration, Period
from pendulum.tz.timezone import FixedTimezone

from app.middlewares.i18n import i18n
from app.models.sleep_record import SleepRecord

_ = i18n.gettext
datetime_fmtr = pendulum.Formatter()


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


def get_explicit_stats(records: List[SleepRecord], tz, language):
    for record in records:
        dt_created_at = pendulum.instance(record.created_at)
        dt_updated_at = pendulum.instance(record.updated_at)
        interval = Period(dt_created_at, dt_updated_at).as_interval()
        yield (
            f"{as_datetime(dt_created_at, tz, language)}"
            + " - "
            + f"{as_datetime(dt_updated_at, tz, language)}"
            + " -- "
            + hbold(
                _("{hours}h {minutes}min").format(
                    hours=interval.hours, minutes=interval.minutes,
                )
            )
        )


def get_stats_by_day(records: List[SleepRecord], tz, language, mode="week", days=7):
    if mode == "week":
        get_day_func = as_weekday
    elif mode == "month":
        days = days + 1
        get_day_func = as_day
    else:
        return []
    result = [Duration() for i in range(days)]

    latenight_offset = Duration(hours=5)
    offset_tz = FixedTimezone(offset=tz.offset - latenight_offset.in_seconds())
    for record in records:
        dt_created_at = pendulum.instance(record.created_at)
        dt_updated_at = pendulum.instance(record.updated_at)
        interval = Period(dt_created_at, dt_updated_at).as_interval()
        i = int(get_day_func(dt_created_at, offset_tz))
        result[i] = result[i] + interval
    for x in filter(lambda a: a.in_seconds() > 0, result):
        yield x


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


def as_weekday(dt: DateTime, tz):
    return datetime_fmtr.format(dt.in_tz(tz), "d")


def as_day(dt: DateTime, tz):
    return datetime_fmtr.format(dt.in_tz(tz), "D")
