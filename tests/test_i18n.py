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
