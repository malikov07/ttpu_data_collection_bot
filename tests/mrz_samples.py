"""Builders for valid MRZ lines and synthetic document images (test data only)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.services.mrz import check_digit

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def td3(
    *,
    surname="ALIYEV",
    given="VALI",
    number="AB1234567",
    nationality="UZB",
    dob="050321",
    sex="M",
    expiry="310520",
    personal="32103051234567",
) -> list[str]:
    l1 = (f"P<UZB{surname}<<{given.replace(' ', '<')}" + "<" * 44)[:44]
    personal = (personal + "<" * 14)[:14]
    pcheck = check_digit(personal) if personal.strip("<") else "<"
    body = number + check_digit(number) + nationality + dob + check_digit(dob) + sex + expiry + check_digit(expiry) + personal + pcheck
    composite = number + check_digit(number) + dob + check_digit(dob) + expiry + check_digit(expiry) + personal + pcheck
    return [l1, body + check_digit(composite)]


def td1(
    *,
    surname="KARIMOVA",
    given="DILNOZA",
    number="AD1234567",
    dob="040715",
    sex="F",
    expiry="340714",
    pinfl="41507041234567",
) -> list[str]:
    opt1 = (pinfl + "<" * 15)[:15]
    l1 = "I<UZB" + number + check_digit(number) + opt1
    opt2 = "<" * 11
    l2_body = dob + check_digit(dob) + sex + expiry + check_digit(expiry) + "UZB" + opt2
    composite = number + check_digit(number) + opt1 + dob + check_digit(dob) + expiry + check_digit(expiry) + opt2
    l2 = l2_body + check_digit(composite)
    l3 = (f"{surname}<<{given}" + "<" * 30)[:30]
    return [l1, l2, l3]


def document_image(
    mrz: list[str],
    *,
    labels: list[str] | None = None,
    blur: float = 0.0,
    rotate: float = 0.0,
    width: int = 1400,
) -> bytes:
    """A passport-like page: photo box, printed fields, MRZ at the bottom."""
    height = 1000
    im = Image.new("RGB", (width, height), (232, 238, 228))
    d = ImageDraw.Draw(im)
    mono = ImageFont.truetype(MONO, 40 if len(mrz[0]) > 40 else 52)
    sans = ImageFont.truetype(SANS, 28)
    d.rectangle([60, 120, 380, 540], fill=(190, 200, 210))
    for i, text in enumerate(labels or ["REPUBLIC OF UZBEKISTAN", "PASSPORT"]):
        d.text((420, 140 + i * 55), text, font=sans, fill=(30, 30, 60))
    top = height - 70 * len(mrz) - 60
    for i, line in enumerate(mrz):
        d.text((60, top + i * 70), line, font=mono, fill=(10, 10, 10))
    if rotate:
        im = im.rotate(rotate, expand=True, fillcolor=(80, 80, 80))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def plain_image(width=800, height=600, color=(200, 180, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()
