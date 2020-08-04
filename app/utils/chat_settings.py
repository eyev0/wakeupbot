from typing import Tuple

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.markdown import hbold, hcode, hitalic

from app.middlewares.i18n import i18n
from app.models.chat import Chat
from app.models.user import User

cb_chat_settings = CallbackData("chat", "id", "property", "value")
cb_user_settings = CallbackData("user", "property", "value")

_ = i18n.gettext

FLAG_STATUS = ["❌", "✅"]


def get_user_settings_markup(
    chat: Chat, user: User
) -> Tuple[str, InlineKeyboardMarkup]:
    return (
        _("Personal settings"),
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_("Bedtime reminder: {reminder}").format(
                            reminder=user.reminder
                        ),
                        callback_data=cb_user_settings.new(
                            property="bedtime_reminder", value="set"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("Time zone: {timezone}").format(timezone=user.timezone),
                        callback_data=cb_user_settings.new(
                            property="time_zone", value="set"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("{status} Do not disturb").format(
                            status=FLAG_STATUS[user.do_not_disturb]
                        ),
                        callback_data=cb_user_settings.new(
                            property="do_not_disturb", value="switch"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("{flag} Language").format(
                            flag=i18n.AVAILABLE_LANGUAGES[chat.language].flag
                        ),
                        callback_data=cb_user_settings.new(
                            property="language", value="change"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("Done"),
                        callback_data=cb_user_settings.new(
                            property="done", value="true"
                        ),
                    )
                ],
            ]
        ),
    )


def get_chat_settings_markup(
    telegram_chat: types.Chat, chat: Chat
) -> Tuple[str, InlineKeyboardMarkup]:
    return (
        _("Settings for chat {chat_title}").format(
            chat_title=hbold(telegram_chat.title)
        ),
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_("{status} Join filter").format(
                            status=FLAG_STATUS[chat.join_filter]
                        ),
                        callback_data=cb_chat_settings.new(
                            id=chat.id, property="join", value="switch"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("{flag} Language").format(
                            flag=i18n.AVAILABLE_LANGUAGES[chat.language].flag
                        ),
                        callback_data=cb_chat_settings.new(
                            id=chat.id, property="language", value="change"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_("Done"),
                        callback_data=cb_chat_settings.new(
                            id=chat.id, property="done", value="true"
                        ),
                    )
                ],
            ]
        ),
    )


async def get_bedtime_reminder_markup(user):
    text = [
        _("Your current bedtime reminder: {reminder}\n").format(reminder=user.reminder),
        _("Enter new time ("),
        hitalic(_("example: ")),
        hcode("21,22:30"),
        "):",
    ]
    markup = types.InlineKeyboardMarkup()
    callback_factory = cb_user_settings.new
    markup.add(
        types.InlineKeyboardButton(
            _("Reset"),
            callback_data=callback_factory(property="bedtime_reminder", value="reset"),
        ),
        types.InlineKeyboardButton(
            _("Cancel"),
            callback_data=callback_factory(property="bedtime_reminder", value="cancel"),
        ),
    )
    return markup, text


async def get_timezone_markup(user):
    text = [
        _("Your current time zone: {timezone}\n").format(timezone=user.timezone),
        _("Enter your time zone ("),
        hitalic(_("example: ")),
        hcode("+1,+10:00,-3:30"),
        "):",
    ]
    markup = types.InlineKeyboardMarkup()
    callback_factory = cb_user_settings.new
    markup.add(
        types.InlineKeyboardButton(
            _("Cancel"),
            callback_data=callback_factory(property="time_zone", value="cancel"),
        )
    )
    return markup, text
