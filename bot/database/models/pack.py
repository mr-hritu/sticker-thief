from sqlalchemy import Column, String, Integer, Boolean

from ..base import Base, engine
from constants.stickers import StickerType as PackType


class Pack(Base):
    __tablename__ = 'packs'

    pack_id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    title = Column(String)
    name = Column(String)
    type = Column(Integer)
    # deprecated: kept for backward compatibility
    is_animated = Column(Boolean, default=False)

    def __init__(self, user_id, title, name, pack_type: int):
        self.user_id = user_id
        self.title = title
        self.name = name
        self.type = pack_type

    def is_pack_static(self):
        return self.type == PackType.STATIC or (not self.type and not self.is_animated)

    def is_pack_animated(self):
        return self.type == PackType.ANIMATED or self.is_animated

    def is_pack_video(self):
        return self.type == PackType.VIDEO


Base.metadata.create_all(engine)
