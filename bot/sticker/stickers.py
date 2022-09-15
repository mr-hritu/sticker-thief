import logging
import re
import sys
import tempfile

# noinspection PyPackageRequirements
from typing import Union, Optional

from telegram import Sticker, Document, InputFile, Bot, Message, File, MessageEntity
# noinspection PyPackageRequirements
from telegram.error import BadRequest, TelegramError

from constants.stickers import StickerType, MimeType
from ..utils import utils
from ..utils.pyrogram import get_sticker_emojis
from .error import EXCEPTIONS

logger = logging.getLogger('StickerFile')


class MessageScaffold:
    def __init__(self, sticker: Sticker):
        self.sticker = sticker
        self.document = None


class StickerFile:
    DEFAULT_EMOJI = '🎭'

    def __init__(self, message: Union[Message, MessageScaffold], emojis: Optional[list] = None):
        self.type = None
        self.sticker: Union[Sticker, Document] = message.sticker or message.document
        self.sticker_tempfile = tempfile.SpooledTemporaryFile()  # bytes object to pass to the api

        if self.is_sticker() and not self.sticker.is_animated and not self.sticker.is_video:
            self.type = StickerType.STATIC
        elif self.is_sticker() and self.sticker.is_animated:
            self.type = StickerType.ANIMATED
        elif self.is_sticker() and self.sticker.is_video:
            self.type = StickerType.VIDEO
        elif self.is_document(MimeType.PNG):
            self.type = StickerType.STATIC
        elif self.is_document(MimeType.WEBM):
            self.type = StickerType.VIDEO
        else:
            raise ValueError("could not detect sticker type")

        if emojis:
            # user-specified emojis has been passed
            # eg. the user sent some emojis before sending the sticker
            self.emojis = emojis
        elif self.is_sticker() and not self.sticker.emoji:
            logger.info("the sticker doesn't have a pack, using default emoji")
            self.emojis = [self.DEFAULT_EMOJI]
        else:
            self.emojis = get_sticker_emojis(message) or [self.DEFAULT_EMOJI]

        logger.debug('emojis: %s', self.emojis)

    @classmethod
    def from_entity(cls, custom_emoji: MessageEntity.CUSTOM_EMOJI, bot: Bot):
        sticker: Sticker = bot.get_custom_emoji_stickers([custom_emoji.custom_emoji_id])[0]
        fake_message = MessageScaffold(sticker)

        return cls(fake_message)

    @property
    def file_unique_id(self):
        return self.sticker.file_unique_id

    @property
    def api_arg_name(self):
        if self.is_animated_sticker():
            return "tgs_sticker"
        elif self.is_animated_sticker():
            return "webm_sticker"
        else:
            return "png_sticker"

    def is_document(self, mime_type: Optional[str] = None):
        is_document = isinstance(self.sticker, Document)

        if not is_document:
            return False
        elif not mime_type:
            return True
        else:
            return self.sticker.mime_type.startswith(mime_type)

    def is_sticker(self):
        return isinstance(self.sticker, Sticker)

    def is_static_sticker(self):
        return self.type == StickerType.STATIC

    def is_animated_sticker(self):
        return self.type == StickerType.ANIMATED

    def is_video_sticker(self):
        return self.type == StickerType.VIDEO

    def type_str(self):
        if self.type == StickerType.STATIC:
            return "static"
        elif self.type == StickerType.ANIMATED:
            return "animated"
        elif self.type == StickerType.VIDEO:
            return "video"
        else:
            return "unknown"

    def get_extension(self, png=False, dot=False):
        prefix = "." if dot else ""
        if self.type == StickerType.STATIC:
            return f"{prefix}webp" if not png else f"{prefix}png"
        elif self.type == StickerType.ANIMATED:
            return f"{prefix}tgs"
        elif self.type == StickerType.VIDEO:
            return f"{prefix}webm"

    def get_emojis_str(self) -> str:
        if not isinstance(self.emojis, (list, tuple)):
            raise ValueError('StickerFile.emojis is not of type list/tuple (type: {})'.format(type(self.emojis)))

        return "".join(self.emojis)

    def sticker_tempfile_seek(self):
        self.sticker_tempfile.seek(0)
        return self.sticker_tempfile

    def get_input_file(self):
        """returns a telegram InputFile"""
        if self.is_animated_sticker():
            extension = "tgs"
        elif self.is_video_sticker():
            extension = "webm"
        else:
            extension = "webp"

        self.sticker_tempfile.seek(0)  # just to make sure

        return InputFile(self.sticker_tempfile, filename=f"{self.file_unique_id}.{extension}")

    def download(self, max_size: Optional[int] = None):
        logger.debug('downloading sticker')
        new_file: File = self.sticker.get_file()

        logger.debug('downloading to bytes object')
        new_file.download(out=self.sticker_tempfile)
        self.sticker_tempfile.seek(0)

        if max_size and self.is_document(MimeType.PNG):
            # try to resize if the passed file is a document
            self.sticker_tempfile = utils.resize_png(self.sticker_tempfile, max_size=max_size)

    def close(self):
        # noinspection PyBroadException
        try:
            self.sticker_tempfile.close()
        except Exception as e:
            logger.error('error while trying to close sticker tempfile: %s', str(e))

    def __repr__(self):
        return 'StickerFile object of original origin {} (type: {})'.format(
            'Sticker' if self.is_sticker() else 'Document',
            self.type_str()
        )
