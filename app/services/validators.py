from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# Latin + Cyrillic letters (incl. Uzbek Oʻ/Gʻ written with any apostrophe variant), spaces, hyphens.
_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-яЁёЎўҚқҒғҲҳ'ʻʼ‘’`\- ]+$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_GROUP_RE = re.compile(r"^[A-Za-z0-9А-Яа-яЁё][A-Za-z0-9А-Яа-яЁё_\-.]{0,31}$")


class ValidationError(ValueError):
    """Raised with an i18n key describing the problem."""

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


_NAME_PART_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-яЁёЎўҚқҒғҲҳ'ʻʼ‘’`\- ]{2,64}$")


def pretty_name(value: str) -> str:
    """ALIYEV -> Aliyev; O'G'LI -> Oʻgʻli (Uzbek apostrophe)."""
    words = []
    for word in value.replace("`", "'").replace("’", "'").replace("ʻ", "'").replace("ʼ", "'").split():
        w = "-".join(p[:1].upper() + p[1:].lower() for p in word.split("-"))
        w = re.sub(r"(?i)([og])'", lambda m: m.group(1) + "ʻ", w)
        if words and w.lower() in ("oʻgʻli", "qizi"):  # "Karim oʻgʻli"
            w = w.lower()
        words.append(w)
    return " ".join(words)


def normalize_name_part(raw: str) -> str:
    """One name (surname, given name or patronymic), prettified."""
    value = " ".join(raw.split())
    if not _NAME_PART_RE.match(value):
        raise ValidationError("err.name_part")
    return pretty_name(value)


def normalize_full_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not (5 <= len(name) <= 100) or not _NAME_RE.match(name):
        raise ValidationError("err.name")
    parts = [p for p in name.split(" ") if p.strip("-'ʻʼ‘’`")]
    if len(parts) < 2 or any(len(p) < 2 for p in parts):
        raise ValidationError("err.name")
    # Only fix capitalisation when the user typed everything in one case.
    if name.isupper() or name.islower():
        name = " ".join(_capitalize(p) for p in name.split(" "))
    return name


def _capitalize(word: str) -> str:
    return "-".join(p[:1].upper() + p[1:].lower() for p in word.split("-"))


_DATE_FORMATS = ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y", "%d,%m,%Y")


def parse_birth_date(raw: str, *, min_age: int, max_age: int, today: date | None = None) -> date:
    text = " ".join(raw.strip().split())
    value = None
    for fmt in _DATE_FORMATS:
        try:
            value = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue
    if value is None:
        # Accept compact forms like 21032005
        digits = re.sub(r"\D", "", text)
        if len(digits) == 8:
            try:
                value = datetime.strptime(digits, "%d%m%Y").date()
            except ValueError:
                pass
    if value is None:
        raise ValidationError("err.date_format")
    age = age_on(value, today or date.today())
    if not (min_age <= age <= max_age):
        raise ValidationError("err.age", min=min_age, max=max_age)
    return value


def age_on(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def normalize_phone(raw: str) -> str:
    """Return the phone in E.164 form (+998901234567)."""
    text = raw.strip()
    if re.search(r"[^\d+\-() .]", text):
        raise ValidationError("err.phone")
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:  # local Uzbek number without country code
        digits = "998" + digits
    if digits.startswith("998"):
        if len(digits) != 12:
            raise ValidationError("err.phone")
    elif not (text.startswith("+") or text.startswith("00")) or not (8 <= len(digits) <= 15):
        raise ValidationError("err.phone")
    return "+" + digits


def format_phone(phone: str) -> str:
    """+998901234567 -> +998 90 123 45 67 (other countries are returned as-is)."""
    if phone.startswith("+998") and len(phone) == 13:
        d = phone[4:]
        return f"+998 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}"
    return phone


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise ValidationError("email.invalid")
    return email


@dataclass(slots=True)
class GroupNames:
    valid: list[str]
    invalid: list[str]


def parse_group_names(raw: str) -> GroupNames:
    valid: list[str] = []
    invalid: list[str] = []
    for chunk in re.split(r"[\n,;]+", raw):
        name = "-".join(chunk.upper().split())
        if not name:
            continue
        target = valid if _GROUP_RE.match(name) else invalid
        if name not in target:
            target.append(name)
    return GroupNames(valid, invalid)
