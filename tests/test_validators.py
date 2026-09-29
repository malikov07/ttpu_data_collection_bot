from datetime import date

import pytest

from app.services.validators import (
    ValidationError,
    format_phone,
    normalize_email,
    normalize_full_name,
    normalize_phone,
    parse_birth_date,
    parse_group_names,
)

TODAY = date(2026, 9, 27)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Aliyev Vali Karimovich", "Aliyev Vali Karimovich"),
        ("  aliyev   vali  ", "Aliyev Vali"),
        ("ALIYEV VALI", "Aliyev Vali"),
        ("Иванов Иван Иванович", "Иванов Иван Иванович"),
        ("G'ulomov Oybek", "G'ulomov Oybek"),
        ("Oʻrinboyev Gʻayrat", "Oʻrinboyev Gʻayrat"),
        ("Smith-Jones Anna", "Smith-Jones Anna"),
        ("Ўринов Қодир", "Ўринов Қодир"),
    ],
)
def test_name_ok(raw, expected):
    assert normalize_full_name(raw) == expected


@pytest.mark.parametrize("raw", ["Vali", "A B", "Vali123 Aliyev", "=HYPERLINK(1) x", "", "x" * 120])
def test_name_bad(raw):
    with pytest.raises(ValidationError):
        normalize_full_name(raw)


@pytest.mark.parametrize(
    "raw", ["21.03.2005", "21/03/2005", "21-03-2005", "2005-03-21", "21032005", " 21.03.2005 "]
)
def test_birth_date_formats(raw):
    assert parse_birth_date(raw, min_age=14, max_age=70, today=TODAY) == date(2005, 3, 21)


def test_birth_date_invalid():
    with pytest.raises(ValidationError) as e:
        parse_birth_date("31.02.2005", min_age=14, max_age=70, today=TODAY)
    assert e.value.key == "err.date_format"


def test_birth_date_age_bounds():
    with pytest.raises(ValidationError) as e:
        parse_birth_date("01.01.2020", min_age=14, max_age=70, today=TODAY)
    assert e.value.key == "err.age"
    assert e.value.params == {"min": 14, "max": 70}


@pytest.mark.parametrize(
    "raw",
    ["+998901234567", "998901234567", "901234567", "+998 (90) 123-45-67", "00998901234567", "90 123 45 67"],
)
def test_phone_uz(raw):
    assert normalize_phone(raw) == "+998901234567"


def test_phone_foreign():
    assert normalize_phone("+7 916 123 45 67") == "+79161234567"


@pytest.mark.parametrize("raw", ["12345", "+99890123456", "abc", "79161234567", "+1"])
def test_phone_bad(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_format_phone():
    assert format_phone("+998901234567") == "+998 90 123 45 67"


def test_email():
    assert normalize_email(" Tutor@Gmail.com ") == "tutor@gmail.com"
    with pytest.raises(ValidationError):
        normalize_email("not-an-email")


def test_group_names():
    r = parse_group_names("se-24-01, SE-24-02\nME 24 01\n\nbad name!, se-24-01")
    assert r.valid == ["SE-24-01", "SE-24-02", "ME-24-01"]
    assert r.invalid == ["BAD-NAME!"]
