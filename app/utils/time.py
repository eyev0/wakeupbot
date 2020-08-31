from typing import Union

import pendulum
from loguru import logger
from pendulum import DateTime, Duration
from pendulum.tz.timezone import FixedTimezone

datetime_fmtr = pendulum.Formatter()
latenight_offset = Duration(hours=5)
VISUAL_GRACE_TIME = 0.1
SLEEP_HOURS = 6
SLEEP_MINUTES = 30


def parse_tz(timezone: str) -> Union[FixedTimezone, None]:
    try:
        sign = timezone[0]
        if sign not in ["-", "+"]:
            raise ValueError
        offset = duration_from_timezone(timezone)
        return pendulum.tz.fixed_timezone(int(sign + "1") * offset.in_seconds())
    except ValueError as e:
        logger.info(f"Wrong timezone format: {timezone}")
        raise e


def duration_from_timezone(timezone: str) -> Duration:
    hours, *minutes = timezone[1:].split(":", maxsplit=1)
    minutes = minutes[-1] if minutes else "0"
    duration = pendulum.Duration(hours=int(hours), minutes=int(minutes))
    return duration


def parse_time(time: str) -> Union[DateTime, None]:
    try:
        hours, *minutes = time.split(":", maxsplit=1)
        minutes = minutes[-1] if minutes else "0"
        return DateTime(1970, 1, 1, hour=int(hours), minute=int(minutes))
    except ValueError as e:
        logger.info(f"Wrong time format: {time}")
        raise e


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
