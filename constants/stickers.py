class StickerType:
    STATIC = 10
    ANIMATED = 20
    VIDEO = 30


class MimeType:
    PNG = "image/png"
    WEBM = "video/webm"


class MaxPackSize:
    STATIC = 120
    ANIMATED = 50
    VIDEO = 120


STICKER_TYPE_DESC = {
    StickerType.STATIC: "static",
    StickerType.ANIMATED: "animated",
    StickerType.VIDEO: "video"
}

MAX_PACK_SIZE = {
    StickerType.STATIC: MaxPackSize.STATIC,
    StickerType.ANIMATED: MaxPackSize.ANIMATED,
    StickerType.VIDEO: MaxPackSize.VIDEO
}
