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
from bot.database.base import session_scope
from bot.database.models.pack import Pack
from ...utils import decorators
from ...utils import utils

logger = logging.getLogger(__name__)

PACK_SUFFIX = f"_by_{stickersbot.bot.username}"

DUMMY_EMOJI = "🧱"  # possibly an emoji that nobody would use


def check_pack_name(user_id: int, pack_name: str, context: CallbackContext) -> [None, str]:
    pack_link = utils.name2link(pack_name, context.bot.username)

    if not re.search(r"^[a-z0-9][a-z0-9_]+[a-z0-9]$", pack_name, re.I):  # needs to be improved
        return Strings.READD_INVALID_PACK_NAME_PATTERN

    if not pack_name.endswith(PACK_SUFFIX):
        return Strings.READD_WRONG_PACK_NAME.format(pack_link, PACK_SUFFIX)

    with session_scope() as session:
        pack_exists = session.query(Pack).filter_by(name=pack_name, user_id=user_id).first() is not None

    if pack_exists:
        return Strings.READD_PACK_EXISTS.format(pack_link)


def process_pack(pack_name: str, update: Update, context: CallbackContext):
    pack_link = utils.name2link(pack_name, context.bot.username)

    warning_text = check_pack_name(update.effective_user.id, pack_name, context)
    if warning_text:
        update.message.reply_html(warning_text)
        return Status.WAITING_STICKER_OR_PACK_NAME

    refresh_dummy_file = False
    if context.user_data.get("dummy_png_file", None):
        now = datetime.datetime.utcnow()
        # refresh every two weeks
        refresh_on = context.user_data["dummy_png_file"]["generated_on"] + datetime.timedelta(14)
        if now > refresh_on:
            refresh_dummy_file = True
        else:
            dummy_png: File = context.user_data["dummy_png_file"]["file"]
    else:
        refresh_dummy_file = True

    if refresh_dummy_file:
        logger.debug("refreshing dummy png file")
        with open("assets/dummy_sticker.png", "rb") as f:
            dummy_png: File = context.bot.upload_sticker_file(update.effective_user.id, f)

        context.user_data["dummy_png_file"] = {"file": dummy_png, "generated_on": datetime.datetime.utcnow()}

    try:
        context.bot.add_sticker_to_set(
            user_id=update.effective_user.id,
            name=pack_name,
            png_sticker=dummy_png.file_id,
            emojis=DUMMY_EMOJI
        )
        logger.debug("successfully added dummy sticker to pack <%s>", pack_name)
    except (TelegramError, BadRequest) as e:
        error_message = e.message.lower()
        if "stickerset_invalid" in error_message:
            update.message.reply_html(Strings.READD_PACK_INVALID.format(pack_link))
            return Status.WAITING_STICKER_OR_PACK_NAME
        else:
            logger.error("/readd: api error while adding dummy sticker to pack <%s>: %s", pack_name, e.message)
            update.message.reply_html(Strings.READD_UNKNOWN_API_EXCEPTION.format(pack_link, e.message))
            return Status.WAITING_STICKER_OR_PACK_NAME

    sticker_set: StickerSet = context.bot.get_sticker_set(pack_name)
    if sticker_set.stickers[-1].emoji == DUMMY_EMOJI:
        sticker_to_remove = sticker_set.stickers[-1]
    else:
        logger.warning("dummy emoji and the emoji of the last sticker in the set do not match")
        sticker_to_remove = None

    pack_row = Pack(
        user_id=update.effective_user.id,
        name=sticker_set.name,
        title=sticker_set.title,
        is_animated=sticker_set.is_animated
    )
    with session_scope() as session:
        session.add(pack_row)

    stickerset_title_link = utils.stickerset_title_link(sticker_set)
    update.message.reply_html(
        Strings.READD_SAVED.format(stickerset_title_link)
    )

    # We do this here to let the API figure out we just added the sticker with that file_id to the pack
    # it will raise an exception anyway though (Sticker_invalid)
    # we might just ignore it. The user now can manage the pack, and can remove the dummy sticker manually
    # Also, it might be the case (IT *IS* THE CASE) that the dummy sticker added to the pack gets its own file_id, so
    # the file_id returned by upload_sticker_file should be used to remove the sticker.
    # We then use the file_id of the last sticker in the pack, but I guess we can't be 100% sure
    # the get_sticker_set request returned the pack with also the dummy sticker we added one second before
    if not sticker_to_remove:
        # the dummy emoji and the emoji of the last sticker in the pack did not match
        update.message.reply_html(Strings.READD_DUMMY_STICKER_NOT_REMOVED)
    else:
        try:
            context.bot.delete_sticker_from_set(sticker=sticker_to_remove.file_id)
            logger.debug("successfully removed dummy sticker from pack <%s>", pack_name)
        except (TelegramError, BadRequest) as e:
            error_message = e.message.lower()
            if "sticker_invalid" in error_message:
                update.message.reply_html(Strings.READD_DUMMY_STICKER_NOT_REMOVED)
            else:
                logger.error("/readd: api error while removing dummy sticker from pack <%s>: %s", pack_name, e.message)
                update.message.reply_html(Strings.READD_DUMMY_STICKER_NOT_REMOVED_UNKNOWN.format(error_message))

    return ConversationHandler.END


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_readd_command(update: Update, context: CallbackContext):
    logger.info('/readd')

    if not context.args:
        update.message.reply_text(Strings.READD_WAITING_STICKER_OR_PACK_NAME)

        return Status.WAITING_STICKER_OR_PACK_NAME

    pack_name = context.args[0].lower().replace("https://t.me/addstickers/", "").replace("t.me/addstickers/", "")

    return process_pack(pack_name, update, context)


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_waiting_pack_static_sticker(update: Update, context: CallbackContext):
    logger.info('/readd: static sticker received')

    sticker: Sticker = update.message.sticker
    if not sticker.set_name:
        update.message.reply_html(Strings.READD_STICKER_NO_PACK)

        return Status.WAITING_STICKER_OR_PACK_NAME

    return process_pack(sticker.set_name, update, context)


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_waiting_pack_animated_sticker(update: Update, context: CallbackContext):
    logger.info('/readd: animated sticker received')

    update.message.reply_html(Strings.READD_STICKER_ANIMATED)

    return Status.WAITING_STICKER_OR_PACK_NAME


@decorators.action(ChatAction.TYPING)
@decorators.restricted
@decorators.failwithmessage
@decorators.logconversation
def on_waiting_pack_unexpected_message(update: Update, context: CallbackContext):
    logger.info('/readd: unexpected message')

    update.message.reply_html(Strings.READD_UNEXPECTED_MESSAGE)

    return Status.WAITING_STICKER_OR_PACK_NAME


stickersbot.add_handler(ConversationHandler(
    name='readd_command',
    persistent=False,
    entry_points=[CommandHandler(['readd', 'rea', 'ra'], on_readd_command)],
    states={
        Status.WAITING_STICKER_OR_PACK_NAME: [
            MessageHandler(CustomFilters.static_sticker, on_waiting_pack_static_sticker),
            MessageHandler(CustomFilters.animated_sticker, on_waiting_pack_animated_sticker),
            MessageHandler(Filters.all & ~CustomFilters.done_or_cancel, on_waiting_pack_unexpected_message),
        ],
        ConversationHandler.TIMEOUT: [MessageHandler(Filters.all, on_timeout)]
    },
    fallbacks=[CommandHandler(['cancel', 'c', 'done', 'd'], cancel_command)],
    # conversation_timeout=15 * 60
))
