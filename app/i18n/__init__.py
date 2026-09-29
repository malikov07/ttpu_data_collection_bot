"""Tiny dictionary-based i18n.

Usage::

    _ = Translator(Language.UZ)
    _("reg.name")
    _("err.age", min=14, max=70)
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.db.models import Language
from app.i18n import en, ru, uz

log = logging.getLogger(__name__)

DEFAULT_LANGUAGE = Language.UZ

TEXTS: dict[Language, dict[str, str]] = {
    Language.UZ: uz.TEXTS,
    Language.RU: ru.TEXTS,
    Language.EN: en.TEXTS,
}

LANGUAGE_PROMPT = "🇺🇿 Tilni tanlang\n🇷🇺 Выберите язык\n🇬🇧 Choose your language"


def t(lang: Language | str | None, key: str, /, **kwargs: object) -> str:
    lang = Language(lang) if lang else DEFAULT_LANGUAGE
    text = TEXTS[lang].get(key)
    if text is None:
        log.warning("Missing translation %s:%s", lang, key)
        text = TEXTS[Language.EN].get(key, key)
    return text.format(**kwargs) if kwargs else text


@lru_cache
def variants(key: str) -> frozenset[str]:
    """All translations of a key — used to match reply-keyboard buttons in any language."""
    return frozenset(texts[key] for texts in TEXTS.values() if key in texts)


@lru_cache
def menu_buttons() -> frozenset[str]:
    """Every button label in every language: never treat them as free-text input."""
    return frozenset(
        text for texts in TEXTS.values() for key, text in texts.items() if key.startswith("btn.")
    )


class Translator:
    __slots__ = ("lang",)

    def __init__(self, lang: Language | str | None) -> None:
        self.lang = Language(lang) if lang else DEFAULT_LANGUAGE

    def __call__(self, key: str, /, **kwargs: object) -> str:
        return t(self.lang, key, **kwargs)
