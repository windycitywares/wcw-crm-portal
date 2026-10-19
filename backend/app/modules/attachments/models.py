from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Attachment(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A file kept against any registered record (customer, ticket, deal …), like a note with a body
    that isn't text.

    The link is polymorphic on purpose: the same `(entity_type, entity_id)` pair the notes and timeline
    use means one table serves every record type, and a feature that can hold a note can hold a file.

    `sha256` is the file's own name on the disk (see `app.integrations.files`), so the same photo sent
    twice is stored once and two rows may point at one stored file — which is why the stored file goes
    only with the last row that pointed at it (`AttachmentService.delete`). `filename` is what the
    sender called it and is only ever shown or handed back, never used to find anything.

    `message_id` says which of the record's messages carried it when a customer sent it (the conversation
    can point back to that message); a file a member of staff added has none. It is a plain id, not a
    foreign key: this block knows nothing about the module that owns the message.
    """

    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_entity", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(20))  # how it got here: email today, upload/chat later
