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
import numpy as np

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


def get_correct_size(sizes, max_size: int = 512):
    i = 0 if sizes[0] > sizes[1] else 1  # i: index of the biggest size
    new = [None, None]
    new[i] = max_size
    rateo = max_size / sizes[i]
    # print(rateo)
    new[1 if i == 0 else 0] = int(math.floor(sizes[1 if i == 0 else 0] * round(rateo, 4)))

    # logger.debug('correct sizes: %dx%d', new[0], new[1])
    return tuple(new)


def resize_pil_image(im: Image, max_size: int = 512) -> Tuple[ImageType, bool]:
    resized = False

    logger.debug('original image size: %s', im.size)
    if (im.size[0] > max_size or im.size[1] > max_size) or (im.size[0] != max_size and im.size[1] != max_size):
        logger.debug('resizing file because one of the sides is > %dpx or at least one side is not %dpx', max_size, max_size)
        correct_size = get_correct_size(im.size, max_size=max_size)
        im = im.resize(correct_size, Image.ANTIALIAS)
        resized = True
    else:
        logger.debug('original size is ok')

    return im, resized


def resize_pil_image_square(im: Image, size: int = 100) -> Tuple[ImageType, bool]:
    resized = False

    logger.debug('original image size: %s', im.size)
    if im.size[0] != size or im.size[1] != size:
        logger.debug('resizing file because the sides are != %dpx', size)
        im = im.resize((size, size), Image.ANTIALIAS)
        resized = True
    else:
        logger.debug('original size is ok')

    return im, resized


def crop_transparency_2(im: Image) -> ImageType:
    # https://stackoverflow.com/a/44703169

    np_array = np.array(im)
    blank_px = [255, 255, 255, 0]
    mask = np_array != blank_px
    coords = np.argwhere(mask)
    x0, y0, z0 = coords.min(axis=0)
    x1, y1, z1 = coords.max(axis=0) + 1
    cropped_box = np_array[x0:x1, y0:y1, z0:z1]
    cropped_pil_image = Image.fromarray(cropped_box, 'RGBA')
    print(cropped_pil_image.width, cropped_pil_image.height)
    return cropped_pil_image


def debug_print_image(image_data_bw):
    # will print the image with X and O
    test_string = ""
    for column in image_data_bw:
        for row in column:
            test_string += "░" if row == 255 else "█"
        test_string += "\n"
    print(test_string)


def crop_transparency_1(im: Image) -> ImageType:
    # https://stackoverflow.com/a/37942933

    image_data = np.asarray(im)
    try:
        image_data_bw = image_data[:, :, 3]  # just extract the alpha value
    except IndexError as ie:
        # numpy can't extract the 3rd index, probably because there is no alpha channel
        # return the image itself
        logger.warning("error while extracting the alpha channel values: %s", str(ie))
        return im.copy()  # we need to return a new object and not the old one, because it iwll be closed later

    # debug_print_image(image_data_bw)

    # print(image_data_bw)
    # print(np.where(image_data_bw.max(axis=0) > 0))
    # print(im.getpixel((0, 0)))

    # the original code was filtering anything with alpha vlaue > 0, see stack overflow url
    # it makes sense to filter naything > 0, but in our case it doesn't work: we need to filter anything that
    # doesn't have any alpha gradient. For some reason, many sticker's tranparent pixel actually have
    # an alpha value slightly above 0
    non_empty_columns = np.where(image_data_bw.max(axis=0) == 255)[0]  # filter columns with non-255 alpha value
    non_empty_rows = np.where(image_data_bw.max(axis=1) == 255)[0]

    # print("non_empty_columns", non_empty_columns)
    # print("non_empty_rows", non_empty_rows)

    crop_box = (min(non_empty_rows), max(non_empty_rows), min(non_empty_columns), max(non_empty_columns))
    # print(crop_box)

    image_data_new = image_data[crop_box[0]:crop_box[1] + 1, crop_box[2]:crop_box[3] + 1, :]

    new_image = Image.fromarray(image_data_new)

    return new_image


def crop_transparency_3(im: Image) -> ImageType:
    # https://stackoverflow.com/a/61952048

    a = np.array(im)[:, :, :3]  # keep RGB only
    m = np.any(a != [255, 255, 255], axis=2)
    coords = np.argwhere(m)
    y0, x0, y1, x1 = *np.min(coords, axis=0), *np.max(coords, axis=0)
    crop_box = (x0, y0, x1+1, y1+1)

    print(crop_box)
    im2 = im.crop(crop_box)
    return im2


def resize_pil_image_square_crop(im: Image, size: int = 100) -> Tuple[ImageType, bool]:
    im = im.resize((size, size), Image.ANTIALIAS)
    logger.debug("getbox(): %s", im.getbbox())

    new_image = crop_transparency_1(im)

    im.close()

    return new_image, True


def resize_png(png_file, max_size: int = 512) -> tempfile.SpooledTemporaryFile:
    im = Image.open(png_file)

    im, resized = resize_pil_image(im, max_size)

    if not resized:
        logger.debug('original size is ok')
        png_file.seek(0)
        return png_file

    resized_tempfile = tempfile.SpooledTemporaryFile()

    im.save(resized_tempfile, 'png')
    im.close()

    resized_tempfile.seek(0)

    return resized_tempfile


def resize_png_square(png_file, size: int = 100) -> tempfile.SpooledTemporaryFile:
    im = Image.open(png_file)

    im = im.resize((size, size), Image.ANTIALIAS)

    resized_tempfile = tempfile.SpooledTemporaryFile()

    im.save(resized_tempfile, 'png')
    im.close()

    resized_tempfile.seek(0)

    return resized_tempfile


def webp_to_png(webp_bo, resize=True, max_size: int = 512, square=False, crop=False) -> tempfile.SpooledTemporaryFile:
    logger.info('preparing png')

    im = Image.open(webp_bo)  # try to open bytes object

    logger.debug('original image size: %s', im.size)
    if resize:
        if square and not crop:
            logger.debug("square: true, crop: false")
            im, _ = resize_pil_image_square(im, size=max_size)
        elif square and crop:
            # crop the image by removing transparent borders
            logger.debug("square: true, crop: true")
            im, _ = resize_pil_image_square_crop(im, size=max_size)
        else:
            logger.debug("square: false")
            im, _ = resize_pil_image(im, max_size=max_size)

    converted_tempfile = tempfile.SpooledTemporaryFile()

    logger.debug('saving PIL image object as tempfile')
    im.save(converted_tempfile, 'png')
    im.close()

    converted_tempfile.seek(0)

    return converted_tempfile

