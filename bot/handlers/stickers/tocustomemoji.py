import datetime
import logging
import re

# noinspection PyPackageRequirements
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    Filters
)
# noinspection PyPackageRequirements
from telegram import ChatAction, Update, Sticker, File, StickerSet
# noinspection PyPackageRequirements
from telegram.error import BadRequest, TelegramError

from bot import stickersbot
from bot.strings import Strings
from ..conversation_statuses import Status
from ..fallback_commands import cancel_command, on_timeout
from ...customfilters import CustomFilters
from bot.stickers import StickerFile
from ...utils import decorators
from ...utils import utils

logger = logging.getLogger(__name__)


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_toemoji_command(update: Update, context: CallbackContext):
    logger.info('/toemoji')

    options = {
        "-c": ("crop", "<code>crop transparent border areas</code>"),
        "-r": ("ignore_rateo", "<code>do not preserve the image's aspect rateo</code>")
    }

    enabled_options_description = utils.check_flags(options, context, pop_existing_flags=True)

    update.message.reply_text(Strings.TO_EMOJI_WAITING_STATIC_STICKER)
    if enabled_options_description:
        update.message.reply_html(f"{Strings.ENABLED_FLAGS}{' + '.join(enabled_options_description)}")

    return Status.WAITING_STICKER


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_sticker_received(update: Update, context: CallbackContext):
    logger.info('/toemoji: stickers received')

    sticker_file = StickerFile(message=update.message)
    sticker_file.download()

    crop = "crop" in context.user_data
    ignore_rateo = "ignore_rateo" in context.user_data
    png_file = utils.webp_to_png(sticker_file.sticker_tempfile, max_size=100, square=True, crop=crop, ignore_rateo=ignore_rateo)

    update.message.reply_document(png_file, filename=f"{update.message.sticker.file_unique_id}.png")

    return Status.WAITING_STICKER


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_waiting_sticker_unexpected_message(update: Update, context: CallbackContext):
    logger.info('/toemoji: unexpected message')

    update.message.reply_html(Strings.TO_EMOJI_UNEXPECTED_MESSAGE)

    return Status.WAITING_STICKER


stickersbot.add_handler(ConversationHandler(
    name='toemoji_command',
    persistent=False,
    entry_points=[CommandHandler(['toemoji', 'tocustomemoji', 'te'], on_toemoji_command)],
    states={
        Status.WAITING_STICKER: [
            CommandHandler(['toemoji', 'tocustomemoji', 'te'], on_toemoji_command),
            MessageHandler(CustomFilters.static_sticker, on_sticker_received),
            MessageHandler(Filters.all & ~CustomFilters.done_or_cancel, on_waiting_sticker_unexpected_message),
        ],
        ConversationHandler.TIMEOUT: [MessageHandler(Filters.all, on_timeout)]
    },
    fallbacks=[CommandHandler(['cancel', 'c', 'done', 'd'], cancel_command)],
    conversation_timeout=15 * 60
))
