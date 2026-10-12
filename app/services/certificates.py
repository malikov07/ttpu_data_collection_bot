"""Certificates and awards: labels, telling the student about a review."""

from __future__ import annotations

import logging
from html import escape

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Certificate, CertStatus, CertType, User
from app.i18n import t

log = logging.getLogger(__name__)

MAX_PER_STUDENT = 20
# Older certificates have a description in the student's own words ("Mathematics A+").
DESCRIBED = {CertType.NATIONAL, CertType.OLYMPIAD, CertType.OTHER}


def type_label(lang: str | None, cert_type: CertType | str) -> str:
    return t(lang, f"cert.type.{CertType(cert_type).value}")


def describe(lang: str | None, cert_type: CertType | str, result: str | None) -> str:
    """"IELTS"; certificates sent before the score was dropped from the form keep it:
    "IELTS 7.5", "National certificate: Mathematics A+" (plain text)."""
    if not result:
        return type_label(lang, cert_type)
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
