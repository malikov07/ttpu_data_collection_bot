from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Language(StrEnum):
    UZ = "uz"
    RU = "ru"
    EN = "en"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class StaffRole(StrEnum):
    ADMIN = "admin"
    TUTOR = "tutor"
    LEADER = "leader"


class DocumentKind(StrEnum):
    PASSPORT = "passport"  # passport main page, or ID card back (+ front)
    PHOTO = "photo"  # 3x4 portrait
    CV = "cv"


class DocType(StrEnum):
    PASSPORT = "passport"
    ID_CARD = "id_card"


def _enum(e: type[StrEnum]) -> Enum:
    # Store enum *values* as plain strings so the DB stays readable and portable.
    return Enum(e, native_enum=False, length=16, values_callable=lambda x: [m.value for m in x])


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


class User(Base):
    """Every Telegram user who has ever talked to the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[Language | None] = mapped_column(_enum(Language))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    students: Mapped[list[Student]] = relationship(back_populates="group")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # Names as in the document (Latin). full_name is kept for search and sorting.
    last_name: Mapped[str] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(64))
    middle_name: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[Gender] = mapped_column(_enum(Gender))
    phone: Mapped[str] = mapped_column(String(20))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    # Identity document (read from the MRZ)
    doc_type: Mapped[DocType | None] = mapped_column(_enum(DocType))
    doc_number: Mapped[str | None] = mapped_column(String(20), index=True)
    doc_expiry: Mapped[date | None] = mapped_column(Date)
    pinfl: Mapped[str | None] = mapped_column(String(14), index=True)
    nationality: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()
    group: Mapped[Group] = relationship(back_populates="students")
    documents: Mapped[list[Document]] = relationship(
        back_populates="student", cascade="all, delete-orphan", order_by="Document.kind"
    )

    def document(self, kind: DocumentKind) -> Document | None:
        return next((d for d in self.documents if d.kind == kind), None)

    def set_names(self, last: str, first: str, middle: str | None) -> None:
        self.last_name, self.first_name, self.middle_name = last, first, middle or None
        self.full_name = " ".join(p for p in (last, first, middle) if p)


class Document(Base):
    """Files submitted by a student for one document.

    Files come from Telegram (``type`` photo/document, ``file_id``) or from the
    website (``type`` upload, ``path`` relative to the uploads directory).
    An ID card has two files: back (with the MRZ) and front.
    """

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("student_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    kind: Mapped[DocumentKind] = mapped_column(_enum(DocumentKind))
    # [{"file_id", "unique_id", "type", "mime", "name", "size", "path"?, "side"?}]
    files: Mapped[list[dict]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    student: Mapped[Student] = relationship(back_populates="documents")


class Account(Base):
    """A staff member: signs in to the website with username + password and
    uses the bot's staff features after /login in Telegram."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(128))
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Temporary passwords set by an admin must be replaced at first sign-in.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]

    roles: Mapped[list[Staff]] = relationship(
        back_populates="account", cascade="all, delete-orphan", order_by="Staff.role"
    )
    user: Mapped[User | None] = relationship()

    @property
    def label(self) -> str:
        return self.display_name or self.username


class Staff(Base):
    """A role of an account: admin, tutor (all groups) or leader of one group."""

    __tablename__ = "staff"
    __table_args__ = (UniqueConstraint("account_id", "role", "group_id", name="uq_staff_account_role_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    role: Mapped[StaffRole] = mapped_column(_enum(StaffRole))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    account: Mapped[Account] = relationship(back_populates="roles")
    group: Mapped[Group | None] = relationship()


class KeyValue(Base):
    """Small persistent settings (runtime preferences)."""

    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class FsmRecord(Base):
    """Conversation state (e.g. a half-filled registration form) per chat."""

    __tablename__ = "fsm_states"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(128))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditLog(Base):
    """Who did what, from the bot or the website."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    # account username for staff, "tg:123456" for students in the bot
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)


class WebSession(Base):
    """A signed-in browser. Only a hash of the cookie token is stored."""

    __tablename__ = "web_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip: Mapped[str | None] = mapped_column(String(64))

    account: Mapped[Account] = relationship()
