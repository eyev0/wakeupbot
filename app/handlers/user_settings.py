import asyncio
from contextlib import suppress

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.filters import OrFilter
from aiogram.dispatcher.filters.state import any_state, default_state
from aiogram.types import ContentTypes
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageNotModified
from loguru import logger
from pendulum import DateTime

from app.middlewares.i18n import i18n
from app.misc import bot, dp
from app.models.user import User
from app.utils import scheduler
from app.utils.states import States
from app.utils.time import VISUAL_GRACE_TIME, parse_time, parse_tz
from app.utils.user_settings import (
    cb_user_settings,
    get_bedtime_reminder_markup,
    get_timezone_markup,
    get_user_settings_markup,
)

_ = i18n.gettext


@dp.message_handler(commands=["settings"])
async def cmd_settings(message: types.Message, user: User):
    logger.info(
        "User {user} wants to configure chat {chat}", user=user.id, chat=user.id
    )
    with suppress(MessageCantBeDeleted):
        await message.delete()

    text, markup = get_user_settings_markup(user)
    await bot.send_message(chat_id=user.id, text=text, reply_markup=markup)


@dp.callback_query_handler(cb_user_settings.filter(property="time_zone", value="set"))
async def cq_time_zone(
    query: types.CallbackQuery, user: User, callback_data: dict, state: FSMContext,
):
    logger.info(
        "User {user} wants set timezone", user=query.from_user.id,
    )
    markup, text = await get_timezone_markup(user)
    await query.answer()
    await query.message.edit_text("".join(text), reply_markup=markup)
    await States.SET_TIMEZONE.set()
    await state.set_data({"original_message_id": query.message.message_id})


@dp.callback_query_handler(
    cb_user_settings.filter(property="bedtime_reminder", value="set")
)
async def cq_bedtime_reminder(
    query: types.CallbackQuery, user: User, callback_data: dict, state: FSMContext,
):
    logger.info(
        "User {user} wants set bedtime reminder", user=query.from_user.id,
    )
    await query.answer()
    markup, text = await get_bedtime_reminder_markup(user)
    await query.message.edit_text("".join(text), reply_markup=markup)
    await States.SET_BEDTIME_REMINDER.set()
    await state.set_data({"original_message_id": query.message.message_id})


@dp.callback_query_handler(cb_user_settings.filter(value="cancel"), state=any_state)
async def cq_cancel_timezone(
    query: types.CallbackQuery, user: User, callback_data: dict, state: FSMContext,
):
    logger.info(
        "User {user} cancelled action {action}",
        user=query.from_user.id,
        action=callback_data["property"],
    )
    await query.answer(_("Action cancelled"))
    text, markup = get_user_settings_markup(user)
    with suppress(MessageNotModified):
        await query.message.edit_text(text, reply_markup=markup)
    await default_state.set()


@dp.callback_query_handler(
    cb_user_settings.filter(property="bedtime_reminder", value="reset"), state=any_state
)
async def cq_reset_reminder(
    query: types.CallbackQuery, user: User, callback_data: dict, state: FSMContext,
):
    logger.info(
        "User {user} reset his reminder", user=query.from_user.id,
    )
    await user.update(reminder="-").apply()
    await scheduler.delete_bedtime_reminder(user)
    await query.answer(_("Reminder reset"))
    text, markup = get_user_settings_markup(user)
    with suppress(MessageNotModified):
        await query.message.edit_text(text, reply_markup=markup)
    await default_state.set()


@dp.message_handler(state=[States.SET_TIMEZONE], content_types=ContentTypes.TEXT)
async def set_timezone(message: types.Message, user: User, state: FSMContext):
    logger.info(
        "User {user} wants to set his timezone preference", user=message.from_user.id,
    )
    try:
        tz = parse_tz(message.text)
    except ValueError:
        await message.answer(_("Wrong format! See examples above"))
        return
    await user.update(timezone=tz.name).apply()
    await scheduler.schedule_bedtime_reminder(user, tz=tz)

    state_data = await state.get_data() or {}
    if original_message_id := state_data.get("original_message_id"):
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await bot.delete_message(user.id, original_message_id)
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await message.delete()
        text, markup = get_user_settings_markup(user)
        await message.answer(
            _("Time zone changed to {timezone}").format(timezone=tz.name),
            reply_markup=markup,
        )
        await state.set_data({})
    await default_state.set()


@dp.message_handler(
    state=[States.SET_BEDTIME_REMINDER], content_types=ContentTypes.TEXT
)
async def set_bedtime_reminder(message: types.Message, user: User, state: FSMContext):
    logger.info(
        "User {user} wants to set his bedtime reminder", user=message.from_user.id,
    )
    try:
        time: DateTime = parse_time(message.text)
    except ValueError:
        await message.answer(_("Wrong time format!"))
        return
    await user.update(reminder=time.format("HH:mm")).apply()
    await scheduler.schedule_bedtime_reminder(user, time=time)

    state_data = await state.get_data() or {}
    if original_message_id := state_data.get("original_message_id"):
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await bot.delete_message(user.id, original_message_id)
        with suppress(MessageCantBeDeleted):
            await asyncio.sleep(VISUAL_GRACE_TIME)
            await message.delete()
        text, markup = get_user_settings_markup(user)
        await message.answer(
            _("Bedtime reminder changed to {time}").format(time=time.format("HH:mm")),
            reply_markup=markup,
        )
        await state.set_data({})
    await default_state.set()


@dp.callback_query_handler(cb_user_settings.filter(property="language", value="change"))
async def cq_language(query: types.CallbackQuery, callback_data: dict):
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
async def cq_choose_language(
    query: types.CallbackQuery, user: User, callback_data: dict
):
    target_language = callback_data["value"]
    logger.info(
        "User {user} set language in chat {chat} to '{language}'",
        user=query.from_user.id,
        chat=user.id,
        language=target_language,
    )

    i18n.ctx_locale.set(target_language)
    await user.update(language=target_language).apply()
    text, markup = get_user_settings_markup(user)
    await query.answer(
        _("Language changed to {new_language}").format(
            new_language=i18n.AVAILABLE_LANGUAGES[target_language].title
        )
    )
    await query.message.edit_text(text, reply_markup=markup)


@dp.callback_query_handler(
    cb_user_settings.filter(property="do_not_disturb", value="switch")
)
async def cq_do_not_disturb(query: types.CallbackQuery, user: User):
    logger.info("User {user} switched DND mode", user=query.from_user.id)
    await query.answer(
        _("Do not disturb mode {mode}").format(
            mode=_("switched on") if not user.do_not_disturb else _("switched off")
        )
    )
    await user.update(do_not_disturb=not user.do_not_disturb).apply()
    text, markup = get_user_settings_markup(user)
    with suppress(MessageNotModified):
        await query.message.edit_text(text, reply_markup=markup)


@dp.callback_query_handler(cb_user_settings.filter(property="done", value="true"))
async def cq_done(query: types.CallbackQuery):
    logger.info(
        "User {user} close settings menu", user=query.from_user.id,
    )
    await query.answer(_("Settings saved"))
    await query.message.delete()
