from typing import List

import pendulum
from aiogram.utils.markdown import hbold
from pendulum import Duration, Period

from app.middlewares.i18n import i18n
from app.models.sleep_record import SleepRecord

_ = i18n.gettext
datetime_fmtr = pendulum.Formatter()


def explicit_stats(records: List[SleepRecord], language):
    for record in records:
        interval = Period(record.created_at, record.updated_at).as_interval()
        dt_created_at = pendulum.instance(record.created_at)
        dt_updated_at = pendulum.instance(record.updated_at)
        yield (
            f"{datetime_fmtr.format(dt_created_at, 'D MMMM, dd HH:mm:ss', language)}"
            + " - "
            + f"{datetime_fmtr.format(dt_updated_at, 'D MMMM, dd HH:mm:ss', language)}"
            + " -- "
            + hbold(
                _("{hours}h {minutes}min").format(
                    hours=interval.hours, minutes=interval.minutes,
                )
            )
        )


def stats_by_day(records: List[SleepRecord], language):
    result = [Duration() for i in range(7)]
    for record in records:
        interval = Period(record.created_at, record.updated_at).as_interval()
        dt_created_at = pendulum.instance(record.created_at)
        day_of_week = int(datetime_fmtr.format(dt_created_at, "d"))
        result[day_of_week] = result[day_of_week] + interval
    for x in filter(lambda a: a.in_seconds() > 0, result):
        yield x
