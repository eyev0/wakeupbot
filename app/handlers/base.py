from aiogram import types
from aiogram.utils.markdown import hbold
from loguru import logger

from app.middlewares.i18n import i18n
from app.misc import dp
from app.models.user import User

_ = i18n.gettext


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message, user: User):
    logger.info("User {user} started conversation with bot", user=message.from_user.id)

    await message.answer(
        _(
            "Hello, {user}!\n\n"
            "Send me '-' when you go to sleep, and '+' when you wake up :) \n"
            "Send '!' to view your weekly stats, '!m' - monthly stats\n"
            "('!m -1' to view stats on previous month etc.)\n\n"
            "Send /help to see list of my commands.\n"
            "You can change language in /settings menu :)"
        ).format(user=hbold(message.from_user.full_name),)
    )

    await user.update(conversation_started=True).apply()


@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message, user: User):
    logger.info("User {user} requested help from bot", user=message.from_user.id)
    text = [
        hbold(_("Here's list of my commands:")),
        _('"-" - Start sleeping'),
        _('"+" - Record your sleep'),
        _('"!" - View weekly stats'),
        _('"!m" - View monthly stats'),
        _('"!m -1" - View previous month\'s stats'),
        _("{command} - Start conversation with bot").format(command="/start"),
        _("{command} - Show this message").format(command="/help"),
        _("{command} - User settings").format(command="/settings"),
    ]
    await message.reply("\n".join(text))


@dp.errors_handler()
async def errors_handler(update: types.Update, exception: Exception):
    try:
        raise exception
    except Exception as e:
        logger.exception("Cause exception {e} in update {update}", e=e, update=update)
    return True
