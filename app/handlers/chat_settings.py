from contextlib import suppress

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.filters import OrFilter
from aiogram.dispatcher.filters.state import any_state, default_state
from aiogram.types import ContentTypes
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageNotModified
from aiogram.utils.markdown import hcode, hitalic
from loguru import logger

from app.middlewares.i18n import i18n
from app.misc import bot, dp
from app.models.chat import Chat
from app.models.user import User
from app.utils.chat_settings import cb_user_settings, get_user_settings_markup
from app.utils.sleep_tracker import parse_time, parse_timezone
from app.utils.states import States

_ = i18n.gettext


@dp.message_handler(commands=["settings"])
async def cmd_chat_settings(message: types.Message, chat: Chat, user: User):
    logger.info(
        "User {user} wants to configure chat {chat}", user=user.id, chat=chat.id
    )
    with suppress(MessageCantBeDeleted):
        await message.delete()

    text, markup = get_user_settings_markup(chat, user)
    await bot.send_message(chat_id=user.id, text=text, reply_markup=markup)


@dp.callback_query_handler(cb_user_settings.filter(property="time_zone", value="set"))
async def cq_user_settings_time_zone(
    query: types.CallbackQuery,
    chat: Chat,
    user: User,
    callback_data: dict,
    state: FSMContext,
):
    logger.info(
        "User {user} wants set timezone", user=query.from_user.id,
    )
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

    await query.answer()
    await query.message.edit_text("".join(text), reply_markup=markup)
    await States.SET_TIMEZONE.set()
    await state.set_data({"original_message_id": query.message.message_id})


@dp.callback_query_handler(
    cb_user_settings.filter(property="bedtime_reminder", value="set")
)
async def cq_user_settings_bedtime_reminder(
    query: types.CallbackQuery,
    chat: Chat,
    user: User,
    callback_data: dict,
    state: FSMContext,
):
    logger.info(
        "User {user} wants set bedtime reminder", user=query.from_user.id,
    )
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
            _("Cancel"),
            callback_data=callback_factory(property="bedtime_reminder", value="cancel"),
        ),
    )

    await query.answer()
    await query.message.edit_text("".join(text), reply_markup=markup)
    await States.SET_BEDTIME_REMINDER.set()
    await state.set_data({"original_message_id": query.message.message_id})


@dp.callback_query_handler(cb_user_settings.filter(value="cancel"), state=any_state)
async def cq_user_settings_cancel_time_zone(
    query: types.CallbackQuery,
    chat: Chat,
    user: User,
    callback_data: dict,
    state: FSMContext,
):
    logger.info(
        "User {user} cancelled action {action}",
        user=query.from_user.id,
        action=callback_data["property"],
    )
    await query.answer(_("Action cancelled"))
    text, markup = get_user_settings_markup(chat, user)
    with suppress(MessageNotModified):
        await query.message.edit_text(text, reply_markup=markup)
    await default_state.set()


@dp.message_handler(state=[States.SET_TIMEZONE], content_types=ContentTypes.TEXT)
async def user_settings_set_time_zone(
    message: types.Message, chat: Chat, user: User, state: FSMContext
):
    logger.info(
        "User {user} wants to set his timezone preference", user=message.from_user.id,
    )
    try:
        tz = parse_timezone(message.text)
    except ValueError:
        await message.answer(_("Wrong format! See examples above"))
        return
    await user.update(timezone=tz.name).apply()

    state_data = await state.get_data() or {}
    if original_message_id := state_data.get("original_message_id"):
        with suppress(MessageCantBeDeleted):
            await bot.delete_message(chat.id, original_message_id)
        with suppress(MessageCantBeDeleted):
            await message.delete()
        text, markup = get_user_settings_markup(chat, user)
        await message.answer(
            _("Time zone changed to {timezone}").format(timezone=tz.name),
            reply_markup=markup,
        )
        await state.set_data({})
    await default_state.set()


@dp.message_handler(
    state=[States.SET_BEDTIME_REMINDER], content_types=ContentTypes.TEXT
)
async def user_settings_set_bedtime_reminder(
    message: types.Message, chat: Chat, user: User, state: FSMContext
):
    logger.info(
        "User {user} wants to set his bedtime reminder", user=message.from_user.id,
    )
    try:
        time = parse_time(message.text).format("HH:mm")
    except ValueError:
        await message.answer(_("Wrong time format!"))
        return
    await user.update(reminder=time).apply()

    state_data = await state.get_data() or {}
    if original_message_id := state_data.get("original_message_id"):
        with suppress(MessageCantBeDeleted):
            await bot.delete_message(chat.id, original_message_id)
        with suppress(MessageCantBeDeleted):
            await message.delete()
        text, markup = get_user_settings_markup(chat, user)
        await message.answer(
            _("Bedtime reminder changed to {time}").format(time=time),
            reply_markup=markup,
        )
        await state.set_data({})
    await default_state.set()


@dp.callback_query_handler(cb_user_settings.filter(property="language", value="change"))
async def cq_chat_settings_language(
    query: types.CallbackQuery, chat: Chat, callback_data: dict
):
    logger.info(
        "User {user} wants to change language", user=query.from_user.id,
    )
    callback_factory = cb_user_settings.new
    markup = types.InlineKeyboardMarkup()
    for code, language in i18n.AVAILABLE_LANGUAGES.items():
        markup.add(
            types.InlineKeyboardButton(
                language.label,
                callback_data=callback_factory(property="language", value=code),
            )
        )

    await query.answer(_("Choose chat language"))
    await query.message.edit_reply_markup(markup)


@dp.callback_query_handler(
    OrFilter(
        *[
            cb_user_settings.filter(property="language", value=code)
            for code in i18n.AVAILABLE_LANGUAGES
        ]
    )
)
async def cq_chat_settings_choose_language(
    query: types.CallbackQuery, chat: Chat, user: User, callback_data: dict
):
    target_language = callback_data["value"]
    logger.info(
        "User {user} set language in chat {chat} to '{language}'",
        user=query.from_user.id,
        chat=chat.id,
        language=target_language,
    )

    i18n.ctx_locale.set(target_language)
    await chat.update(language=target_language).apply()
    text, markup = get_user_settings_markup(chat, user)
    await query.answer(
        _("Language changed to {new_language}").format(
            new_language=i18n.AVAILABLE_LANGUAGES[target_language].title
        )
    )
    await query.message.edit_text(text, reply_markup=markup)


@dp.callback_query_handler(
    cb_user_settings.filter(property="do_not_disturb", value="switch")
)
async def cq_user_settings_do_not_disturb(
    query: types.CallbackQuery, user: User, chat: Chat
):
    logger.info("User {user} switched DND mode", user=query.from_user.id)
    await query.answer(
        _("Do not disturb mode {mode}").format(
            mode=_("switched on") if not user.do_not_disturb else _("switched off")
        )
    )
    await user.update(do_not_disturb=not user.do_not_disturb).apply()
    text, markup = get_user_settings_markup(chat, user)
    with suppress(MessageNotModified):
        await query.message.edit_text(text, reply_markup=markup)


@dp.callback_query_handler(cb_user_settings.filter(property="done", value="true"))
async def cq_chat_settings_done(query: types.CallbackQuery, chat: Chat):
    logger.info(
        "User {user} close settings menu", user=query.from_user.id,
    )
    await query.answer(_("Settings saved"))
    await query.message.delete()
