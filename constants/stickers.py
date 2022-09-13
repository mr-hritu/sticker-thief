class StickerType:
    STATIC = 10
    ANIMATED = 20
    VIDEO = 30


class MimeType:
    PNG = "image/png"
    WEBM = "video/webm"


STICKER_TYPE_DESC = {
    StickerType.STATIC: "static",
    StickerType.ANIMATED: "animated",
    StickerType.VIDEO: "video"
}
