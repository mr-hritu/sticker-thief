import logging
import logging.config
import json
import os
import pickle
from pickle import UnpicklingError
from html import escape
import math
import tempfile
from typing import Tuple

from PIL import Image
from PIL.Image import Image as ImageType  # https://stackoverflow.com/a/58236618/13350541
import emoji
# noinspection PyPackageRequirements
from telegram import Message, Sticker, StickerSet
# noinspection PyPackageRequirements
from telegram.ext import PicklePersistence

logger = logging.getLogger(__name__)


def load_logging_config(file_name='logging.json'):
    with open(file_name, 'r') as f:
        logging_config = json.load(f)

    logging.config.dictConfig(logging_config)


def escape_html(*args, **kwargs):
    return escape(*args, **kwargs)


def name2link(name: str, bot_username=None):
    if bot_username and not name.endswith('_by_' + bot_username):
        name += '_by_' + bot_username

    return 'https://t.me/addstickers/{}'.format(name)


def sticker2link(sticker: Sticker, bot_username=None):
    if not sticker.set_name:
        raise ValueError("<Sticker> object doesn not belong to a pack")

    return name2link(sticker.set_name, bot_username)


def stickerset_title_link(sticker_set: StickerSet):
    return f'<a href="{name2link(sticker_set.name)}">{escape_html(sticker_set.title)}</a>'


def get_emojis(text, as_list=False):
    emojis = [e["emoji"] for e in emoji.emoji_list(text)]
    if as_list:
        return emojis
    else:
        return ''.join(emojis)


def get_emojis_from_message(message: Message) -> [list, None]:
    """Will return a list: either the sticker's emoji (in a list) or the emojis in the document's caption. Will
    return None if the document's caption doesn't have any emoji"""

    if message.sticker:
        if message.sticker.emoji:
            return [message.sticker.emoji]
        else:
            # the sticker doesn't have a pack -> no emoji
            return None
    elif message.document and not message.caption:
        return None
    elif message.document and message.caption:
        emojis_list = get_emojis(message.caption, as_list=True)
        if not emojis_list:
            return None

        return emojis_list


def persistence_object(config_enabled=True, file_path='persistence/data.pickle'):
    if not config_enabled:
        return

    logger.info('unpickling persistence: %s', file_path)
    try:
        # try to load the file
        try:
            with open(file_path, "rb") as f:
                pickle.load(f)
        except FileNotFoundError:
            pass

    except (UnpicklingError, EOFError):
        logger.warning('deserialization failed: removing persistence file and trying again')
        os.remove(file_path)

    return PicklePersistence(
        filename=file_path,
        store_chat_data=False,
        store_bot_data=False
    )


def get_correct_size(sizes, max_side: int = 512):
    i = 0 if sizes[0] > sizes[1] else 1  # i: index of the biggest size
    new = [None, None]
    new[i] = max_side
    rateo = max_side / sizes[i]
    # print(rateo)
    new[1 if i == 0 else 0] = int(math.floor(sizes[1 if i == 0 else 0] * round(rateo, 4)))

    # logger.debug('correct sizes: %dx%d', new[0], new[1])
    return tuple(new)


def resize_pil_image(im: Image, max_side: int = 512) -> Tuple[ImageType, bool]:
    resized = False

    logger.debug('original image size: %s', im.size)
    if (im.size[0] > max_side or im.size[1] > max_side) or (im.size[0] != max_side and im.size[1] != max_side):
        logger.debug('resizing file because one of the sides is > %dpx or at least one side is not %dpx', max_side, max_side)
        correct_size = get_correct_size(im.size)
        im = im.resize(correct_size, Image.ANTIALIAS)
        resized = True
    else:
        logger.debug('original size is ok')

    return im, resized


def resize_png(png_file, max_side: int = 512) -> tempfile.SpooledTemporaryFile:
    im = Image.open(png_file)

    im, resized = resize_pil_image(im, max_side)

    if not resized:
        logger.debug('original size is ok')
        png_file.seek(0)
        return png_file

    resized_tempfile = tempfile.SpooledTemporaryFile()

    im.save(resized_tempfile, 'png')
    im.close()

    resized_tempfile.seek(0)

    return resized_tempfile


def webp_to_png(webp_bo, resize=True) -> tempfile.SpooledTemporaryFile:
    logger.info('preparing png')

    im = Image.open(webp_bo)  # try to open bytes object

    logger.debug('original image size: %s (resize: %s)', im.size, resize)
    if resize:
        im, _ = resize_pil_image(im)

    converted_tempfile = tempfile.SpooledTemporaryFile()

    logger.debug('saving PIL image object as tempfile')
    im.save(converted_tempfile, 'png')
    im.close()

    converted_tempfile.seek(0)

    return converted_tempfile

