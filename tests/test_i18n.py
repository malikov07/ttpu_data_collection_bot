import re
import string

import pytest

from app.i18n import TEXTS, Translator, variants
from app.db.models import Language

FORMATTER = string.Formatter()


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in FORMATTER.parse(text) if name}


def test_all_languages_have_same_keys():
    keys = {lang: set(texts) for lang, texts in TEXTS.items()}
    reference = keys[Language.EN]
    for lang, ks in keys.items():
        assert ks == reference, f"{lang}: missing={reference - ks} extra={ks - reference}"


@pytest.mark.parametrize("lang", list(Language))
def test_placeholders_match_english(lang):
    for key, text in TEXTS[Language.EN].items():
        assert placeholders(TEXTS[lang][key]) == placeholders(text), f"{lang}:{key}"


@pytest.mark.parametrize("lang", list(Language))
def test_html_tags_balanced(lang):
    for key, text in TEXTS[lang].items():
        for tag in ("b", "i", "code"):
            opened = len(re.findall(rf"<{tag}>", text))
            closed = len(re.findall(rf"</{tag}>", text))
            assert opened == closed, f"{lang}:{key} <{tag}>"


def test_button_labels_unique_per_language():
    # Reply-keyboard buttons are matched by text, so they must not collide.
    for lang, texts in TEXTS.items():
        labels = [v for k, v in texts.items() if k.startswith("btn.") and k not in {"btn.prev", "btn.next"}]
        assert len(labels) == len(set(labels)), lang


def test_translator_formats():
    assert "7" in Translator("en")("reg.cv", max=7)
    assert variants("btn.students") == {"👥 Students", "👥 Talabalar", "👥 Студенты"}


def test_bot_profile_texts_fit_telegram_limits():
    from app.i18n import t

    for lang in Language:
        assert 0 < len(t(lang, "bot.name")) <= 64
        assert 0 < len(t(lang, "bot.short_description")) <= 120
        assert 0 < len(t(lang, "bot.description")) <= 512


async def test_profile_is_only_updated_when_it_changed():
    from aiogram import Bot, methods
    from aiogram.types import BotDescription, BotName, BotShortDescription

    from app.commands import setup_profile
    from app.i18n import t
    from tests.conftest import RecordingSession

    class Session(RecordingSession):
        async def make_request(self, bot, method, timeout=None):
            self.requests.append(method)
            lang = method.language_code if hasattr(method, "language_code") else None
            current = lambda key: t(lang or "uz", key) if lang != "ru" else "old"  # noqa: E731
            if isinstance(method, methods.GetMyName):
                return BotName(name=current("bot.name"))
            if isinstance(method, methods.GetMyShortDescription):
                return BotShortDescription(short_description=current("bot.short_description"))
            if isinstance(method, methods.GetMyDescription):
                return BotDescription(description=current("bot.description"))
            return True

    session = Session()
    await setup_profile(Bot("123456:TEST", session=session))
    sets = [r for r in session.requests if type(r).__name__.startswith("SetMy")]
    assert {(type(r).__name__, r.language_code) for r in sets} == {
        ("SetMyName", "ru"), ("SetMyShortDescription", "ru"), ("SetMyDescription", "ru"),
    }
    assert sets[0].name == "TTPU: данные студентов"
