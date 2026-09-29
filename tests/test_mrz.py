from datetime import date

import pytest

from app.services.mrz import MRZError, check_digit, find_mrz
from tests.mrz_samples import td1, td3


def test_check_digit_icao_example():
    # ICAO 9303 specimen: document number L898902C3 -> check digit 6
    assert check_digit("L898902C3") == "6"
    assert check_digit("740812") == "2"


def test_passport_td3():
    data = find_mrz(["REPUBLIC OF UZBEKISTAN", *td3()])
    assert data.format == "TD3" and data.is_passport
    assert (data.last_name, data.first_name) == ("ALIYEV", "VALI")
    assert data.document_number == "AB1234567"
    assert data.birth_date == date(2005, 3, 21)
    assert data.expiry_date == date(2031, 5, 20)
    assert data.sex == "male"
    assert data.nationality == "UZB"
    assert data.personal_number == "32103051234567"


def test_id_card_td1():
    data = find_mrz(td1())
    assert data.format == "TD1" and not data.is_passport
    assert (data.last_name, data.first_name) == ("KARIMOVA", "DILNOZA")
    assert data.document_number == "AD1234567"
    assert data.birth_date == date(2004, 7, 15)
    assert data.sex == "female"
    assert data.personal_number == "41507041234567"


def test_ocr_confusions_are_repaired():
    l1, l2 = td3()
    # O instead of 0 in the birth date, S instead of 5, "«" instead of "<", spaces
    noisy2 = l2.replace("0503213", "O5O3213").replace("31052053", "31O52O53")
    noisy1 = l1.replace("<<VALI", "««VALI")
    data = find_mrz([noisy1, " ".join([noisy2[:20], noisy2[20:]])])
    assert data.birth_date == date(2005, 3, 21)
    assert data.first_name == "VALI"


def test_trailing_filler_misread_as_k():
    l1, l2 = td3()
    l1 = l1[:30] + "K<KK<<<<<<<<<K"
    assert find_mrz([l1, l2]).first_name == "VALI"


def test_missing_trailing_fillers():
    l1, l2 = td3()
    assert find_mrz([l1.rstrip("<"), l2]).last_name == "ALIYEV"


def test_wrong_digit_is_rejected():
    l1, l2 = td3()
    broken = l2[:15] + ("7" if l2[15] != "7" else "8") + l2[16:]  # birth date digit misread
    with pytest.raises(MRZError) as e:
        find_mrz([l1, broken])
    assert str(e.value) == "check_digit"


def test_no_mrz():
    with pytest.raises(MRZError) as e:
        find_mrz(["REPUBLIC OF UZBEKISTAN", "PASSPORT", "Some text"])
    assert str(e.value) == "not_found"


def test_multi_word_given_name():
    data = find_mrz(td3(given="ANNA MARIA"))
    assert data.first_name == "ANNA MARIA"


def test_partial_mrz():
    l1, l2 = td3()
    with pytest.raises(MRZError) as e:
        find_mrz(["PASSPORT", l2])  # names line cut off
    assert str(e.value) == "partial"
