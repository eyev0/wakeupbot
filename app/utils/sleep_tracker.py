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


def subtract_diff(diff: str, now_dt: DateTime, period: str) -> DateTime:
    new_dt = now_dt
    command, *args = diff.split(maxsplit=1)
    args = args[-1] if args else ""
    if args:
        try:
            diff = -int(args)
        except ValueError as e:
            logger.error(e)
            raise e
        if period == "month":
            new_dt = now_dt.subtract(months=diff)
        elif period == "week":
            new_dt = now_dt.subtract(weeks=diff)
    return new_dt


def get_explicit_stats(records: List[SleepRecord], tz, language):
    for record in records:
        dt_created_at = pendulum.instance(record.created_at).in_timezone(tz)
        dt_updated_at = pendulum.instance(record.updated_at).in_timezone(tz)
        interval = Period(dt_created_at, dt_updated_at).as_interval()
        yield (
            f"{as_datetime(dt_created_at, language)}"
            + " - "
            + f"{as_datetime(dt_updated_at, language)}"
            + " -- "
            + hbold(
                _("{hours}h {minutes}min").format(
                    hours=interval.hours, minutes=interval.minutes,
                )
            )
        )


def get_stats_by_day(records: List[SleepRecord], tz, language):
    result = [Duration() for i in range(7)]
    for record in records:
        dt_created_at = pendulum.instance(record.created_at).in_timezone(tz)
        dt_updated_at = pendulum.instance(record.updated_at).in_timezone(tz)
        interval = Period(dt_created_at, dt_updated_at).as_interval()
        day_of_week = int(datetime_fmtr.format(dt_created_at, "d"))
        result[day_of_week] = result[day_of_week] + interval
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


def as_short_date(dt: DateTime, locale):
    return datetime_fmtr.format(dt, "D MMM", locale)


def as_month(dt: DateTime, locale):
    return datetime_fmtr.format(dt, "MMMM YYYY", locale)


def as_datetime(dt: DateTime, locale):
    return datetime_fmtr.format(dt, "D MMMM, dd HH:mm:ss", locale)
