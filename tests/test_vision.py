"""Real OCR / face models on synthetic images (no mocks, runs offline).

conftest only replaces the async wrappers; these tests call the sync internals."""

from __future__ import annotations

import io
from datetime import date

from PIL import Image

from app.services import vision
from tests.mrz_samples import document_image, plain_image, shrink, td1, td2, td3

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
    assert read(plain_image(400, 260)).error in {"blurry", "not_found"}  # small is fine if readable
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


def test_reads_small_downloaded_e_id_images():
    """e-ID images downloaded from my.gov.uz are small (e.g. 856x540) but sharp."""
    for side in (540, 380, 300):
        r = read(shrink(document_image(td1()), side))
        assert r.error is None and r.mrz.document_number == "AD1234567", side
    assert read(shrink(document_image(td3()), 320)).error is None
    error, _ = vision._check_id_front(shrink(document_image(td1()), 300))
    assert error == "no_face"  # read and checked, not refused as "too small"


def test_foreign_documents():
    # A German passport: no PINFL, and "Dietrich" (a name) is not a patronymic.
    page = document_image(
        td3(surname="MUELLER", given="DIETRICH", number="C01X00T47", nationality="D<<", personal="", issuing="D<<"),
        labels=["BUNDESREPUBLIK DEUTSCHLAND", "DIETRICH"],
    )
    r = read(page)
    assert r.error is None and (r.mrz.last_name, r.mrz.first_name) == ("MUELLER", "DIETRICH")
    assert r.mrz.issuing_state == "D" and r.mrz.pinfl is None and r.patronymic is None
    # A visa sticker has an MRZ too, but it isn't the passport page.
    assert read(document_image(td3(code="V<", issuing="UZB", surname="SMITH", given="JOHN", personal=""))).error == "visa"
    # TD2 card: photo and MRZ on one side, so no front side is asked for.
    r = read(document_image(td2()))
    assert r.error is None and r.mrz.format == "TD2" and not r.mrz.needs_front


def test_single_name_passport():
    from app.services.mrz import find_mrz

    lines = td3(surname="", given="SITI", number="X12345678", nationality="IDN", issuing="IDN", personal="")
    mrz = find_mrz(lines)
    assert (mrz.last_name, mrz.first_name) == ("SITI", "")
