"""Data-access helpers. Functions take an open AsyncSession and never commit;
the caller (a bot middleware or a web route) owns the transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from aiogram.types import User as TgUser
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Account,
    AuditLog,
    Certificate,
    CertStatus,
    CertType,
    Document,
    DocumentKind,
    DocType,
    Gender,
    Group,
    KeyValue,
    Staff,
    StaffRole,
    Student,
    User,
    WebSession,
    utcnow,
)
from app.services.passwords import generate_password, hash_password


def as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo; everything we store is UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- users


async def upsert_user(session: AsyncSession, tg: TgUser) -> User:
    user = await session.get(User, tg.id)
    if user is None:
        user = User(id=tg.id, username=tg.username, first_name=tg.first_name)
        session.add(user)
    elif (
        user.username != tg.username
        or user.first_name != tg.first_name
        or as_utc(user.last_seen_at) < utcnow() - timedelta(minutes=10)
    ):
        user.username = tg.username
        user.first_name = tg.first_name
        user.last_seen_at = utcnow()
    await session.flush()
    return user


# -------------------------------------------------------------------------- groups


@dataclass(slots=True)
class GroupStat:
    group: Group
    students: int


async def list_groups(session: AsyncSession, *, active_only: bool = True, ids: list[int] | None = None) -> list[Group]:
    stmt = select(Group).order_by(Group.name)
    if active_only:
        stmt = stmt.where(Group.is_active.is_(True))
    if ids is not None:
        stmt = stmt.where(Group.id.in_(ids))
    return list((await session.scalars(stmt)).all())


async def list_group_stats(session: AsyncSession, group_ids: list[int] | None = None) -> list[GroupStat]:
    counts = (
        select(Student.group_id, func.count(Student.id).label("n")).group_by(Student.group_id).subquery()
    )
    stmt = (
        select(Group, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.group_id == Group.id)
        .order_by(Group.name)
    )
    if group_ids is not None:
        stmt = stmt.where(Group.id.in_(group_ids))
    else:
        stmt = stmt.where(Group.is_active.is_(True))
    return [GroupStat(g, n) for g, n in (await session.execute(stmt)).all()]


async def get_group_by_name(session: AsyncSession, name: str) -> Group | None:
    return await session.scalar(select(Group).where(func.upper(Group.name) == name.upper()))


async def add_groups(session: AsyncSession, names: list[str]) -> tuple[list[str], list[str]]:
    """Create groups (reactivating hidden ones). Returns (added, already_existing)."""
    added, existing = [], []
    for name in names:
        group = await get_group_by_name(session, name)
        if group is None:
            session.add(Group(name=name))
            added.append(name)
        elif not group.is_active:
            group.is_active = True
            added.append(group.name)
        else:
            existing.append(group.name)
    await session.flush()
    return added, existing


@dataclass(slots=True)
class GroupImport:
    added: list[str]
    existing: list[str]
    missing: list[str]  # active groups here that the source doesn't list (e.g. graduated)


async def import_groups(session: AsyncSession, names: list[str]) -> GroupImport:
    """Add groups from an outside list (EduPage). Nothing is hidden or deleted."""
    added, existing = await add_groups(session, names)
    listed = {n.upper() for n in names}
    missing = [g.name for g in await list_groups(session) if g.name.upper() not in listed]
    return GroupImport(added, existing, missing)


async def remove_group(session: AsyncSession, group: Group) -> bool:
    """Delete an empty group; hide a group that has students.

    Returns True if the group was deleted, False if only hidden.
    """
    n = await session.scalar(select(func.count(Student.id)).where(Student.group_id == group.id))
    if n:
        group.is_active = False
        await session.flush()
        return False
    # SQL-level delete: leader roles of the group go via ON DELETE CASCADE.
    await session.execute(delete(Group).where(Group.id == group.id))
    session.expunge(group)
    return True


# ------------------------------------------------------------------------ students


def student_options():
    return (
        selectinload(Student.group),
        selectinload(Student.documents),
        selectinload(Student.certificates),
        selectinload(Student.user),
    )


async def get_student(session: AsyncSession, student_id: int) -> Student | None:
    return await session.scalar(select(Student).where(Student.id == student_id).options(*student_options()))


async def get_student_by_tg(session: AsyncSession, telegram_id: int) -> Student | None:
    return await session.scalar(
        select(Student).where(Student.telegram_id == telegram_id).options(*student_options())
    )


async def find_duplicate_document(
    session: AsyncSession, *, pinfl: str | None, doc_number: str | None, telegram_id: int
) -> Student | None:
    """Another student (different Telegram account) with the same document."""
    conds = []
    if pinfl:
        conds.append(Student.pinfl == pinfl)
    if doc_number:
        conds.append(Student.doc_number == doc_number)
    if not conds:
        return None
    return await session.scalar(
        select(Student).where(or_(*conds), Student.telegram_id != telegram_id).limit(1)
    )


@dataclass(slots=True)
class StudentForm:
    last_name: str
    first_name: str
    middle_name: str | None
    birth_date: date
    gender: Gender
    phone: str
    group_id: int
    doc_type: DocType | None = None
    doc_number: str | None = None
    doc_expiry: date | None = None
    pinfl: str | None = None
    nationality: str | None = None
    documents: dict[DocumentKind, list[dict]] = field(default_factory=dict)


@dataclass(slots=True)
class SaveResult:
    student: Student
    created: bool
    previous_group_id: int | None


async def save_student(session: AsyncSession, telegram_id: int, form: StudentForm) -> SaveResult:
    student = await get_student_by_tg(session, telegram_id)
    created = student is None
    previous_group_id = None if student is None else student.group_id
    if student is None:
        student = Student(telegram_id=telegram_id, documents=[])
        session.add(student)

    student.set_names(form.last_name, form.first_name, form.middle_name)
    student.birth_date = form.birth_date
    student.gender = form.gender
    student.phone = form.phone
    student.group_id = form.group_id
    student.doc_type = form.doc_type
    student.doc_number = form.doc_number
    student.doc_expiry = form.doc_expiry
    student.pinfl = form.pinfl
    student.nationality = form.nationality
    student.updated_at = utcnow()
    for kind, files in form.documents.items():
        set_document_files(student, kind, files)

    await session.flush()
    await session.refresh(student, ["group"])
    return SaveResult(student, created, previous_group_id)


def set_document_files(student: Student, kind: DocumentKind, files: list[dict]) -> bool:
    """Attach new files to a student's document. Returns False if unchanged."""
    doc = student.document(kind)
    if doc is None:
        student.documents.append(Document(kind=kind, files=files))
        return True
    if _file_ids(doc.files) == _file_ids(files):
        return False
    doc.files = files
    return True


def _file_ids(files: list[dict]) -> list[str]:
    return [f.get("unique_id") or f["file_id"] for f in files]


async def count_students(session: AsyncSession, group_id: int | None = None) -> int:
    stmt = select(func.count(Student.id))
    if group_id is not None:
        stmt = stmt.where(Student.group_id == group_id)
    return await session.scalar(stmt) or 0


async def list_students(session: AsyncSession, group_id: int, *, offset: int = 0, limit: int = 10) -> list[Student]:
    stmt = (
        select(Student)
        .where(Student.group_id == group_id)
        .order_by(Student.full_name)
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def search_students(
    session: AsyncSession, query: str, group_ids: list[int] | None, *, limit: int = 30
) -> list[Student]:
    """Case-insensitive search by name, phone, @username, document number or PINFL.

    Filtering happens in Python because SQLite's LOWER() is ASCII-only.
    """
    stmt = select(Student).options(selectinload(Student.group), selectinload(Student.user))
    if group_ids is not None:
        stmt = stmt.where(Student.group_id.in_(group_ids))
    q = query.casefold().lstrip("@").strip()
    q_digits = "".join(ch for ch in q if ch.isdigit())
    result = []
    for s in (await session.scalars(stmt)).all():
        haystack = f"{s.full_name} {s.user.username or ''} {s.doc_number or ''}".casefold()
        if q in haystack or (len(q_digits) >= 4 and (q_digits in s.phone or q_digits in (s.pinfl or ""))):
            result.append(s)
    result.sort(key=lambda s: s.full_name.casefold())
    return result[:limit]


async def delete_student(session: AsyncSession, student: Student) -> None:
    await session.delete(student)
    await session.flush()


# -------------------------------------------------------------------- certificates


def certificate_options():
    return (selectinload(Certificate.student).options(selectinload(Student.group), selectinload(Student.user)),)


async def get_certificate(session: AsyncSession, cert_id: int) -> Certificate | None:
    return await session.scalar(select(Certificate).where(Certificate.id == cert_id).options(*certificate_options()))


async def add_certificate(
    session: AsyncSession, student: Student, cert_type: CertType, result: str, files: list[dict]
) -> Certificate:
    # Setting .student (not appending to student.certificates) never lazy-loads the
    # collection; a loaded collection still gets the new certificate.
    cert = Certificate(student=student, type=cert_type, result=result, files=files, status=CertStatus.PENDING)
    session.add(cert)
    await session.flush()
    return cert


async def list_certificates(
    session: AsyncSession, group_ids: list[int] | None, *, status: CertStatus | None = None, limit: int = 20
) -> list[Certificate]:
    """Newest first, within the given groups (None = all)."""
    stmt = select(Certificate).join(Student, Student.id == Certificate.student_id).options(*certificate_options())
    if group_ids is not None:
        stmt = stmt.where(Student.group_id.in_(group_ids))
    if status is not None:
        stmt = stmt.where(Certificate.status == status)
    stmt = stmt.order_by(Certificate.created_at.desc(), Certificate.id.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def count_certificates(session: AsyncSession, group_ids: list[int] | None, status: CertStatus) -> int:
    stmt = select(func.count(Certificate.id)).join(Student, Student.id == Certificate.student_id).where(Certificate.status == status)
    if group_ids is not None:
        stmt = stmt.where(Student.group_id.in_(group_ids))
    return await session.scalar(stmt) or 0


def review_certificate(cert: Certificate, status: CertStatus, reviewer: str, note: str | None = None) -> None:
    cert.status = status
    cert.note = (note or None) if status == CertStatus.REJECTED else None
    cert.reviewed_by = reviewer
    cert.reviewed_at = utcnow()


# ------------------------------------------------------------------------ accounts


@dataclass(slots=True, frozen=True)
class Access:
    """What a staff member is allowed to see and do."""

    is_admin: bool = False
    is_tutor: bool = False
    leader_group_ids: frozenset[int] = frozenset()
    account_id: int | None = None
    username: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.is_admin or self.is_tutor or bool(self.leader_group_ids)

    @property
    def sees_all(self) -> bool:
        return self.is_admin or self.is_tutor

    def visible_group_ids(self) -> list[int] | None:
        """None means 'all groups'."""
        return None if self.sees_all else sorted(self.leader_group_ids)

    def can_view_group(self, group_id: int) -> bool:
        return self.sees_all or group_id in self.leader_group_ids

    # Tutors edit everything; leaders edit their own group(s).
    can_edit_group = can_view_group

    @property
    def role(self) -> str:
        return "admin" if self.is_admin else "tutor" if self.is_tutor else "leader"


def access_for(account: Account | None, *, env_admin: bool = False) -> Access:
    roles = account.roles if account is not None and account.is_active else []
    return Access(
        is_admin=env_admin or any(r.role == StaffRole.ADMIN for r in roles),
        is_tutor=any(r.role == StaffRole.TUTOR for r in roles),
        leader_group_ids=frozenset(r.group_id for r in roles if r.role == StaffRole.LEADER and r.group_id),
        account_id=account.id if account is not None else None,
        username=account.username if account is not None else None,
    )


def account_options():
    return (
        selectinload(Account.roles).selectinload(Staff.group),
        selectinload(Account.user),
    )


async def get_account(session: AsyncSession, account_id: int) -> Account | None:
    return await session.scalar(select(Account).where(Account.id == account_id).options(*account_options()))


async def get_account_by_username(session: AsyncSession, username: str) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.username == username.lower()).options(*account_options())
    )


async def get_account_by_telegram(session: AsyncSession, telegram_id: int) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.telegram_id == telegram_id).options(*account_options())
    )


async def get_access(session: AsyncSession, telegram_id: int, admin_ids: list[int]) -> Access:
    """Access of a Telegram user in the bot."""
    account = await get_account_by_telegram(session, telegram_id)
    return access_for(account, env_admin=telegram_id in admin_ids)


async def list_accounts(session: AsyncSession) -> list[Account]:
    return list((await session.scalars(select(Account).options(*account_options()).order_by(Account.username))).all())


async def create_account(
    session: AsyncSession,
    *,
    username: str,
    display_name: str | None,
    roles: list[tuple[StaffRole, int | None]],
    password: str | None = None,
) -> tuple[Account, str]:
    """Create an account. Returns it with the (temporary) password in clear text."""
    temp = password or generate_password()
    account = Account(
        username=username,
        display_name=display_name,
        password_hash=hash_password(temp),
        must_change_password=password is None,
        roles=[Staff(role=role, group_id=group_id) for role, group_id in roles],
    )
    session.add(account)
    await session.flush()
    return account, temp


def set_roles(account: Account, roles: list[tuple[StaffRole, int | None]]) -> None:
    wanted = {(r, g) for r, g in roles}
    account.roles = [r for r in account.roles if (r.role, r.group_id) in wanted] + [
        Staff(role=r, group_id=g) for r, g in wanted if not any(x.role == r and x.group_id == g for x in account.roles)
    ]


async def reset_password(session: AsyncSession, account: Account) -> str:
    """Set a new temporary password and sign the account out everywhere."""
    temp = generate_password()
    account.password_hash = hash_password(temp)
    account.must_change_password = True
    await end_sessions(session, account.id)
    return temp


async def set_password(session: AsyncSession, account: Account, password: str, *, keep_session: str | None = None) -> None:
    account.password_hash = hash_password(password)
    account.must_change_password = False
    await end_sessions(session, account.id, except_hash=keep_session)


async def end_sessions(session: AsyncSession, account_id: int, *, except_hash: str | None = None) -> None:
    stmt = delete(WebSession).where(WebSession.account_id == account_id)
    if except_hash:
        stmt = stmt.where(WebSession.token_hash != except_hash)
    await session.execute(stmt)


async def link_telegram(session: AsyncSession, account: Account, telegram_id: int) -> None:
    """Connect a Telegram user to an account (one account per Telegram user)."""
    await session.execute(
        update(Account).where(Account.telegram_id == telegram_id, Account.id != account.id).values(telegram_id=None)
    )
    account.telegram_id = telegram_id
    await session.flush()


async def leader_telegram_ids(session: AsyncSession, group_id: int) -> list[int]:
    """Telegram IDs of the group's leaders (for notifications)."""
    stmt = (
        select(Account.telegram_id)
        .join(Staff, Staff.account_id == Account.id)
        .where(
            Staff.role == StaffRole.LEADER,
            Staff.group_id == group_id,
            Account.is_active.is_(True),
            Account.telegram_id.is_not(None),
        )
    )
    return [tg for tg in (await session.scalars(stmt)).all() if tg]


async def count_admins(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count(func.distinct(Staff.account_id)))
        .join(Account, Account.id == Staff.account_id)
        .where(Staff.role == StaffRole.ADMIN, Account.is_active.is_(True))
    ) or 0


# ------------------------------------------------------------------------------ kv


async def kv_get(session: AsyncSession, key: str) -> str | None:
    row = await session.get(KeyValue, key)
    return row.value if row else None


async def kv_set(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(KeyValue, key)
    if row is None:
        session.add(KeyValue(key=key, value=value))
    else:
        row.value = value
    await session.flush()


# --------------------------------------------------------------------------- audit


async def audit(
    session: AsyncSession,
    actor: str,
    action: str,
    *,
    entity: str | None = None,
    entity_id: int | None = None,
    summary: str | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id, summary=summary, details=details)
    )
    await session.flush()


def tg_actor(telegram_id: int) -> str:
    return f"tg:{telegram_id}"


def actor_of(access: Access, telegram_id: int) -> str:
    """Audit actor for a bot action: the staff account, else the Telegram ID."""
    return access.username or tg_actor(telegram_id)
