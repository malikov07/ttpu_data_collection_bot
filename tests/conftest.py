"""Test harness: a real Dispatcher fed with synthetic updates, a Bot whose HTTP
session records requests instead of calling Telegram, a temporary SQLite DB,
and a scriptable stand-in for the image analysis (OCR / face checks)."""

from __future__ import annotations

import itertools
import os
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio

os.environ.setdefault("BOT_TOKEN", "123456:TEST")

from aiogram import Bot, Dispatcher, methods
from aiogram.client.session.base import BaseSession
from aiogram.types import CallbackQuery, Chat, Contact, Document, Message, MessageEntity, PhotoSize, Update, User

from app.config import Settings
from app.db import create_engine, create_session_factory, init_db, repo
from app.db.fsm_storage import DbStorage
from app.db.models import StaffRole
from app.handlers import admin, common, registration, staff
from app.middlewares import DbSessionMiddleware, UserContextMiddleware
from app.services import vision
from app.services.mrz import find_mrz
from app.services.vision import DocumentResult
from tests.mrz_samples import td1, td3

BOT_USER = User(id=123456, is_bot=True, first_name="TTPU bot", username="ttpu_test_bot")
ROUTERS = (common.router, admin.router, staff.router, registration.router, common.fallback_router)
_ids = itertools.count(1000)


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[methods.TelegramMethod] = []

    async def make_request(self, bot: Bot, method: methods.TelegramMethod, timeout: int | None = None) -> Any:
        self.requests.append(method)
        chat = Chat(id=getattr(method, "chat_id", 0) or 0, type="private")
        now = datetime.now(timezone.utc)
        if isinstance(method, methods.GetMe):
            return BOT_USER
        if isinstance(method, (methods.SendMessage, methods.SendPhoto, methods.SendDocument)):
            return Message(message_id=next(_ids), date=now, chat=chat, text=getattr(method, "text", None))
        if isinstance(method, methods.SendMediaGroup):
            return [Message(message_id=next(_ids), date=now, chat=chat)]
        if isinstance(method, methods.EditMessageText):
            return Message(message_id=method.message_id or 0, date=now, chat=chat, text=method.text)
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError
        yield b""

    async def close(self) -> None:
        pass

    def texts(self, chat_id: int | None = None) -> list[str]:
        out = []
        for r in self.requests:
            text = getattr(r, "text", None) or getattr(r, "caption", None)
            if isinstance(r, (methods.SendMessage, methods.EditMessageText, methods.SendPhoto, methods.SendDocument)) and text:
                if chat_id is None or r.chat_id == chat_id:
                    out.append(text)
        return out

    def last(self, cls=None):
        for r in reversed(self.requests):
            if cls is None or isinstance(r, cls):
                return r
        raise AssertionError(f"no {cls} request")

    def clear(self) -> None:
        self.requests.clear()


class FakeVision:
    """Scriptable results keyed by Telegram file_id (downloads return the id)."""

    def __init__(self) -> None:
        self.documents: dict[str, DocumentResult] = {}
        self.portraits: dict[str, str | None] = {}
        self.fronts: dict[str, tuple[str | None, str | None]] = {}

    async def read_document(self, data: bytes) -> DocumentResult:
        return self.documents.get(data.decode(), DocumentResult("not_found"))

    async def check_portrait(self, data: bytes) -> str | None:
        return self.portraits.get(data.decode(), None)

    async def check_id_front(self, data: bytes) -> tuple[str | None, str | None]:
        return self.fronts.get(data.decode(), (None, None))


def passport_result(**kw) -> DocumentResult:
    patronymic = kw.pop("patronymic", "Karimovich")
    return DocumentResult(None, mrz=find_mrz(td3(**kw)), patronymic=patronymic)


def id_card_result(**kw) -> DocumentResult:
    return DocumentResult(None, mrz=find_mrz(td1(**kw)), patronymic=None)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        bot_token="123456:TEST",
        admin_ids=[1],
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        uploads_dir=tmp_path / "uploads",
    )


class Harness:
    def __init__(self, dp, bot, tg, sessions, fake: FakeVision):
        self.dp, self.bot, self.tg, self.sessions, self.vision = dp, bot, tg, sessions, fake
        self._update_ids = itertools.count(1)

    def user(self, uid: int, first_name: str = "User", username: str | None = None) -> User:
        return User(id=uid, is_bot=False, first_name=first_name, username=username, language_code="en")

    async def feed(self, **kwargs) -> None:
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), **kwargs))

    def _msg(self, user: User, **kwargs) -> Message:
        return Message(
            message_id=next(_ids), date=datetime.now(timezone.utc), chat=Chat(id=user.id, type="private"), from_user=user, **kwargs
        )

    async def text(self, user: User, text: str) -> int:
        entities = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))] if text.startswith("/") else None
        msg = self._msg(user, text=text, entities=entities)
        await self.feed(message=msg)
        return msg.message_id

    async def contact(self, user: User, phone: str, owner_id: int | None = None) -> None:
        c = Contact(phone_number=phone, first_name=user.first_name, user_id=owner_id or user.id)
        await self.feed(message=self._msg(user, contact=c))

    async def photo(self, user: User, file_id: str, size: tuple[int, int] = (1280, 960)) -> None:
        p = PhotoSize(file_id=file_id, file_unique_id=f"u-{file_id}", width=size[0], height=size[1], file_size=1000)
        await self.feed(message=self._msg(user, photo=[p]))

    async def document(self, user: User, name: str, mime: str, size: int = 1000) -> None:
        d = Document(file_id=f"doc-{name}", file_unique_id=f"u-{name}", file_name=name, mime_type=mime, file_size=size)
        await self.feed(message=self._msg(user, document=d))

    async def click(self, user: User, data: str) -> None:
        msg = Message(
            message_id=next(_ids), date=datetime.now(timezone.utc), chat=Chat(id=user.id, type="private"), from_user=BOT_USER, text="…"
        )
        await self.feed(callback_query=CallbackQuery(id=str(next(_ids)), from_user=user, chat_instance="ci", message=msg, data=data))

    def buttons(self) -> list[tuple[str, str | None]]:
        for r in reversed(self.tg.requests):
            markup = getattr(r, "reply_markup", None)
            if markup is not None and hasattr(markup, "inline_keyboard"):
                return [(b.text, b.callback_data or b.url) for row in markup.inline_keyboard for b in row]
        return []

    def button(self, label_part: str) -> str:
        for text, data in self.buttons():
            if label_part in text:
                return data
        raise AssertionError(f"button {label_part!r} not in {self.buttons()}")

    async def create_account(self, username: str, role: StaffRole, group_name: str | None = None, password: str = "Secret123"):
        async with self.sessions() as s:
            group_id = (await repo.get_group_by_name(s, group_name)).id if group_name else None
            account, _ = await repo.create_account(s, username=username, display_name=username.title(), roles=[(role, group_id)], password=password)
            await s.commit()
            return account.id


@pytest.fixture(autouse=True)
def fake_vision(monkeypatch) -> FakeVision:
    fake = FakeVision()
    monkeypatch.setattr(vision, "read_document", fake.read_document)
    monkeypatch.setattr(vision, "check_portrait", fake.check_portrait)
    monkeypatch.setattr(vision, "check_id_front", fake.check_id_front)

    async def fake_download(bot, file_id: str) -> bytes:
        return file_id.encode()

    monkeypatch.setattr(registration, "download", fake_download)
    return fake


@pytest_asyncio.fixture
async def h(settings, fake_vision):
    engine = create_engine(settings.database_url)
    await init_db(engine)
    sessions = create_session_factory(engine)
    tg = RecordingSession()
    bot = Bot(token=settings.bot_token.get_secret_value(), session=tg)
    dp = Dispatcher(storage=DbStorage(sessions), settings=settings)
    dp.update.outer_middleware(DbSessionMiddleware(sessions))
    dp.update.outer_middleware(UserContextMiddleware(settings))
    dp.include_routers(*ROUTERS)
    try:
        yield Harness(dp, bot, tg, sessions, fake_vision)
    finally:
        for r in ROUTERS:  # aiogram routers are module singletons
            r._parent_router = None
        await engine.dispose()


# ----------------------------------------------------------------------------- web


class Web:
    def __init__(self, app, h: Harness):
        import httpx

        self.app, self.h, self._httpx = app, h, httpx

    def client(self):
        transport = self._httpx.ASGITransport(app=self.app, client=("127.0.0.1", 5000))
        return self._httpx.AsyncClient(transport=transport, base_url="http://localhost", headers={"X-Requested-With": "test"})

    async def login(self, username: str, password: str = "Secret123"):
        c = self.client()
        r = await c.post("/api/auth/login", json={"username": username, "password": password})
        return c, r


@pytest_asyncio.fixture
async def web(h, settings):
    from app.web import create_app

    app = create_app(settings=settings, sessions=h.sessions, bot=h.bot, frontend_dist=settings.uploads_dir.parent / "no-dist")
    return Web(app, h)
