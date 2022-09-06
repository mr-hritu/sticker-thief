import datetime
import logging
import re

# noinspection PyPackageRequirements
import tempfile

from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    Filters
)
# noinspection PyPackageRequirements
from telegram import ChatAction, Update, Sticker, File, StickerSet, Message, ParseMode, MessageEntity, InputFile
# noinspection PyPackageRequirements
from telegram.error import BadRequest, TelegramError

from bot import stickersbot
from bot.strings import Strings
from ..conversation_statuses import Status
from ..fallback_commands import cancel_command, on_timeout
from ...customfilters import CustomFilters
from bot.sticker import StickerFile
from ...utils import decorators
from ...utils import utils

logger = logging.getLogger(__name__)


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_tofile_command(update: Update, context: CallbackContext):
    logger.info('/tofile')

    options = {
        "-w": ("webp", "<code>send static stickers as webp and not png</code>")
    }

    enabled_options_description = []
    if context.args:
        for option_key, (user_data_key, description) in options.items():
            if option_key in context.args:
                context.user_data[user_data_key] = True
                enabled_options_description.append(description)
    else:
        # make sure the keys are not in user_data
        for option_key, (user_data_key, _) in options.items():
            context.user_data.pop(user_data_key, None)

    update.message.reply_text(Strings.TO_FILE_WAITING_STICKER)
    if enabled_options_description:
        update.message.reply_html(f"Enabled flags: {' + '.join(enabled_options_description)}")

    return Status.WAITING_STICKER


@decorators.restricted
@decorators.action(ChatAction.UPLOAD_DOCUMENT)
@decorators.failwithmessage
def on_sticker_received(update: Update, context: CallbackContext):
    logger.info('user sent a sticker to convert')

    sticker = StickerFile(context.bot, update.message)
    sticker.download()

    request_kwargs = dict(
        caption=sticker.emojis_str,
        quote=True
    )

    static_sticker_as_webp = "webp" in context.user_data

    if update.message.sticker.is_animated:
        request_kwargs['document'] = sticker.tempfile
        request_kwargs['filename'] = f"{update.message.sticker.file_unique_id}.tgs"
        request_kwargs['disable_content_type_detection'] = True
    elif update.message.sticker.is_video:
        request_kwargs['document'] = sticker.tempfile
        request_kwargs['filename'] = f"{update.message.sticker.file_unique_id}.webm"
        request_kwargs['disable_content_type_detection'] = True
    elif static_sticker_as_webp:
        request_kwargs['document'] = sticker.tempfile
        request_kwargs['filename'] = f"{update.message.sticker.file_unique_id}.webp"
        request_kwargs['disable_content_type_detection'] = True
    else:
        logger.debug("converting webp to png")
        png_file = utils.webp_to_png(sticker.tempfile)

        request_kwargs['document'] = png_file
        request_kwargs['filename'] = f"{update.message.sticker.file_unique_id}.png"

    sent_message: Message = update.message.reply_document(**request_kwargs)
    sticker.close()

    if sent_message.document:
        # only do this when we send the message as document
        # it will be useful to test problems with animated stickers. For example in mid 2020, the API started
        # to consider any animated sticker as invalid ("wrong file type" exception), and they were sent
        # back as file with a specific mimetype ("something something bad animated sticker"). In this way:
        # - sent back as animated sticker: everything ok
        # - sent back as file: there's something wrong with the code/api, better to edit the document with its mimetype
        sent_message.edit_caption(
            caption='{}\n<code>{}</code>'.format(
                sent_message.caption,
                Strings.TO_FILE_MIME_TYPE.format(sent_message.document.mime_type)
            ),
            parse_mode=ParseMode.HTML
        )
    elif sent_message.sticker:
        update.message.reply_text(Strings.ANIMATED_STICKERS_NO_FILE)

    request_kwargs['document'].close()

    return Status.WAITING_STICKER


@decorators.restricted
@decorators.action(ChatAction.UPLOAD_DOCUMENT)
@decorators.failwithmessage
def on_custom_emoji_receive(update: Update, context: CallbackContext):
    logger.info('user sent a custom emoji to convert')

    if len(update.message.entities) > 1:
        update.message.reply_html(Strings.EMOJI_TO_FILE_TOO_MANY_ENTITIES, quote=True)
        return Status.WAITING_STICKER

    sticker: Sticker = context.bot.get_custom_emoji_stickers([update.message.entities[0].custom_emoji_id])[0]

    sticker_file: File = sticker.get_file()

    logger.debug('downloading to bytes object')
    downloaded_tempfile = tempfile.SpooledTemporaryFile()
    sticker_file.download(out=downloaded_tempfile)
    downloaded_tempfile.seek(0)

    if sticker.is_animated:
        extension = "tgs"
    elif sticker.is_video:
        extension = "webm"
    else:
        extension = "webp"
    input_file = InputFile(downloaded_tempfile, filename=f"{sticker.file_unique_id}.{extension}")

    update.message.reply_document(input_file, disable_content_type_detection=True, caption=sticker.emoji, quote=True)
    downloaded_tempfile.close()


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_waiting_sticker_unexpected_message(update: Update, context: CallbackContext):
    logger.info('/tofile: unexpected message')

    update.message.reply_html(Strings.TO_FILE_UNEXPECTED_MESSAGE)

    return Status.WAITING_STICKER


stickersbot.add_handler(ConversationHandler(
    name='tofile_command',
    persistent=False,
    entry_points=[CommandHandler(['tofile', 'tf'], on_tofile_command)],
    states={
        Status.WAITING_STICKER: [
            CommandHandler(['tofile', 'tf'], on_tofile_command),
            MessageHandler(Filters.sticker, on_sticker_received),
            MessageHandler(Filters.entity(MessageEntity.CUSTOM_EMOJI), on_custom_emoji_receive),
            MessageHandler(Filters.all & ~CustomFilters.done_or_cancel, on_waiting_sticker_unexpected_message),
        ],
        ConversationHandler.TIMEOUT: [MessageHandler(Filters.all, on_timeout)]
    },
    fallbacks=[CommandHandler(['cancel', 'c', 'done', 'd'], cancel_command)],
    conversation_timeout=15 * 60
))



