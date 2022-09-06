import logging

# noinspection PyPackageRequirements
import tempfile

from telegram.ext import MessageHandler, Filters, CallbackContext
# noinspection PyPackageRequirements
from telegram import Update, ChatAction, Message, ParseMode, MessageEntity, Sticker, File, InputFile

from bot import stickersbot
from bot.sticker import StickerFile
from bot.strings import Strings
from ...customfilters import CustomFilters
from ...utils import utils
from ...utils import decorators

logger = logging.getLogger(__name__)


@decorators.restricted
@decorators.action(ChatAction.UPLOAD_DOCUMENT)
@decorators.failwithmessage
def on_sticker_receive(update: Update, context: CallbackContext):
    logger.info('user sent a sticker to convert')

    if update.message.sticker.is_animated:
        # do nothing with animated stickers. We keep the code here just for debugging purposes
        return

    sticker = StickerFile(context.bot, update.message)
    sticker.download()

    request_kwargs = dict(
        caption=sticker.emojis_str,
        quote=True
    )

    if update.message.sticker.is_animated:
        request_kwargs['document'] = sticker.tempfile
        request_kwargs['filename'] = f"{update.message.sticker.file_unique_id}.tgs"
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


@decorators.restricted
@decorators.action(ChatAction.UPLOAD_DOCUMENT)
@decorators.failwithmessage
def on_custom_emoji_receive(update: Update, context: CallbackContext):
    logger.info('user sent a custom emoji to convert')

    if len(update.message.entities) > 1:
        update.message.reply_html(Strings.EMOJI_TO_FILE_TOO_MANY_ENTITIES, quote=True)
        return

    sticker: Sticker = context.bot.get_custom_emoji_stickers([update.message.entities[0].custom_emoji_id])[0]
    if sticker.is_video:
        update.message.reply_html(Strings.EMOJI_TO_FILE_VIDEO_NOT_SUPPORTED, quote=True)
        return

    sticker_file: File = sticker.get_file()

    logger.debug('downloading to bytes object')
    downloaded_tempfile = tempfile.SpooledTemporaryFile()
    sticker_file.download(out=downloaded_tempfile)
    downloaded_tempfile.seek(0)

    extension = "webp" if not sticker.is_animated else "tgs"
    input_file = InputFile(downloaded_tempfile, filename=f"{sticker.file_unique_id}.{extension}")

    update.message.reply_document(input_file, disable_content_type_detection=True, caption=sticker.emoji, quote=True)
    downloaded_tempfile.close()


stickersbot.add_handler(MessageHandler(CustomFilters.non_video_sticker, on_sticker_receive))
stickersbot.add_handler(MessageHandler(Filters.entity(MessageEntity.CUSTOM_EMOJI), on_custom_emoji_receive))
