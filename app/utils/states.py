from aiogram.dispatcher.filters.state import State, StatesGroup


class States(StatesGroup):
    SET_TIMEZONE = State()
    SET_BEDTIME_REMINDER = State()
