"""Certificates and awards: result validation, labels, telling the student about a review."""

from __future__ import annotations

import logging
import re
from html import escape

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Certificate, CertStatus, CertType, User
from app.i18n import t
from app.services.validators import ValidationError

log = logging.getLogger(__name__)

MAX_PER_STUDENT = 20
CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
# Tests with a numeric score: (min, max, step)
SCORES: dict[CertType, tuple[float, float, float]] = {
    CertType.IELTS: (0, 9, 0.5),
    CertType.TOEFL: (0, 120, 1),
    CertType.SAT: (400, 1600, 10),
    CertType.DUOLINGO: (10, 160, 5),
}
# Types described in the student's own words ("Mathematics A+", "IMO 2025, silver")
DESCRIBED = {CertType.NATIONAL, CertType.OLYMPIAD, CertType.OTHER}
DESCRIPTION_LENGTH = (3, 100)


def normalize_result(cert_type: CertType, raw: str) -> str:
    """The score, level or description as it will be stored; raises ValidationError."""
    text = " ".join(raw.split())
    if cert_type == CertType.CEFR:
        level = text.upper().replace(" ", "")
        if level not in CEFR_LEVELS:
            raise ValidationError("cefr")
        return level
    if cert_type in SCORES:
        low, high, step = SCORES[cert_type]
        if not re.fullmatch(r"\d{1,4}([.,]\d)?", text):
            raise ValidationError("score")
        value = float(text.replace(",", "."))
        if not low <= value <= high or round(value / step, 6) % 1:
            raise ValidationError("score")
        return f"{value:.1f}" if step < 1 else str(int(value))
    lo, hi = DESCRIPTION_LENGTH
    if not lo <= len(text) <= hi or not any(ch.isalpha() for ch in text):
        raise ValidationError("description")
    return text


def type_label(lang: str | None, cert_type: CertType | str) -> str:
    return t(lang, f"cert.type.{CertType(cert_type).value}")


def describe(lang: str | None, cert_type: CertType | str, result: str) -> str:
    """"IELTS 7.5", "National certificate: Mathematics A+" (plain text)."""
    sep = ": " if CertType(cert_type) in DESCRIBED else " "
    return f"{type_label(lang, cert_type)}{sep}{result}"


def label(lang: str | None, cert: Certificate) -> str:
    return describe(lang, cert.type, cert.result)


async def notify_student(bot: Bot, session: AsyncSession, cert: Certificate) -> None:
    """Tell the student their certificate was accepted or not (best effort)."""
    tg_id = cert.student.telegram_id
    user = await session.get(User, tg_id)
    lang = user.language if user else None
    name = escape(label(lang, cert))
    if cert.status == CertStatus.APPROVED:
        text = t(lang, "cert.notify_approved", cert=name)
    elif cert.status == CertStatus.REJECTED:
        text = t(lang, "cert.notify_rejected", cert=name)
        if cert.note:
            text += "\n" + t(lang, "cert.reason", reason=escape(cert.note))
    else:
        return
    try:
        await bot.send_message(tg_id, text)
    except Exception as e:  # blocked the bot, etc.
        log.debug("Could not notify student %s about certificate %s: %s", tg_id, cert.id, e)
