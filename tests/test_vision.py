"""Real OCR / face models on synthetic images (no mocks, runs offline).

conftest only replaces the async wrappers; these tests call the sync internals."""

from __future__ import annotations

import io
from datetime import date

from PIL import Image

from app.services import vision
from tests.mrz_samples import document_image, plain_image, td1, td3

TODAY = date(2026, 9, 30)


def read(data: bytes):
    return vision._read_document(data, TODAY)


def test_reads_passport_and_suggests_patronymic():
    img = document_image(td3(), labels=["REPUBLIC OF UZBEKISTAN", "Otasining ismi / Patronymic", "KARIMOVICH"])
    r = read(img)
    assert r.error is None
    assert (r.mrz.last_name, r.mrz.first_name, r.mrz.document_number) == ("ALIYEV", "VALI", "AB1234567")
    assert r.mrz.personal_number == "32103051234567"
    assert r.patronymic == "Karimovich"


def test_reads_phone_like_and_sideways_photos():
    assert read(document_image(td3(), blur=0.8, rotate=3, width=1280)).error is None
    assert read(document_image(td3(), rotate=90)).error is None


def test_reads_id_card_back():
    r = read(document_image(td1()))
    assert r.error is None and r.mrz.format == "TD1" and r.mrz.personal_number == "41507041234567"


def test_rejects_bad_photos():
    assert read(document_image(td3(), blur=4.0)).error == "blurry"
    assert read(plain_image()).error in {"blurry", "not_found"}
    assert read(plain_image(300, 200)).error == "too_small"
    assert read(b"not an image").error == "not_image"


def test_expired_document():
    r = read(document_image(td3(expiry="200101")))
    assert r.error == "expired"


def test_portrait_checks():
    assert vision._check_portrait(plain_image(800, 600)) == "not_portrait"
    assert vision._check_portrait(plain_image(200, 260)) == "too_small"
    assert vision._check_portrait(b"junk") == "not_image"
    # A sharp portrait-shaped document page has text but no face.
    page = document_image(td3(), width=1400)
    im = Image.open(io.BytesIO(page)).crop((0, 0, 750, 1000))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    assert vision._check_portrait(buf.getvalue()) == "no_face"
