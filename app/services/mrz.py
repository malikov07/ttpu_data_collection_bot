"""Machine Readable Zone (ICAO 9303) parsing and validation.

Passports (TD3: 2 x 44), ID cards (TD1: 3 x 30) and TD2 documents (2 x 36).
Every field protected by a check digit is verified, so a result is only
returned when the OCR read the document correctly. Typical OCR confusions
(O/0, I/1, B/8 ...) are repaired per field, guided by the check digits.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from datetime import date

_WEIGHTS = (7, 3, 1)
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}
_TO_ALPHA = {v: k for k, v in {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}.items()}
# Characters OCR tends to produce instead of the filler "<"
_FILLER_LOOKALIKES = str.maketrans({"«": "<", "‹": "<", "(": "<", "{": "<", "[": "<", "С": "<", "£": "<", " ": ""})

LINE_LENGTHS = {"TD1": 30, "TD2": 36, "TD3": 44}


class MRZError(ValueError):
    pass


def check_digit(value: str) -> str:
    total = 0
    for i, ch in enumerate(value):
        if ch.isdigit():
            n = int(ch)
        elif "A" <= ch <= "Z":
            n = ord(ch) - 55
        else:  # "<"
            n = 0
        total += n * _WEIGHTS[i % 3]
    return str(total % 10)


def normalize_line(text: str) -> str:
    return text.upper().translate(_FILLER_LOOKALIKES).strip()


def looks_like_mrz(line: str) -> bool:
    if not re.fullmatch(r"[A-Z0-9<]+", line):
        return False
    if len(line) >= 28:
        return line.count("<") >= 2 or line[:1] in "PIAC"
    # Name lines lose their trailing fillers most easily: "P<UZBALIYEV<<VALI"
    return len(line) >= 8 and "<<" in line


def _is_names_line(line: str) -> bool:
    return "<<" in line and not any(ch.isdigit() for ch in line[5:])


@dataclass(slots=True)
class MRZData:
    format: str  # TD1 / TD2 / TD3
    document_code: str  # "P", "I", "ID", "AC" ...
    issuing_state: str
    document_number: str
    nationality: str
    birth_date: date
    sex: str | None  # "male" / "female" / None
    expiry_date: date
    last_name: str
    first_name: str
    personal_number: str | None  # PINFL for Uzbekistan (14 digits)
    lines: list[str] = field(default_factory=list)

    @property
    def is_passport(self) -> bool:
        return self.document_code.startswith("P")


# ------------------------------------------------------------------ field repair


def _digits(s: str) -> str:
    return "".join(_TO_DIGIT.get(c, c) for c in s)


def _alpha(s: str) -> str:
    return "".join(_TO_ALPHA.get(c, c) for c in s)


def _repair_with_check(value: str, check: str, *, numeric: bool) -> tuple[str, str] | None:
    """Return (value, check) fixed so that the check digit matches, or None."""
    check = _digits(check)
    if numeric:
        value = _digits(value)
    if check_digit(value) == check:
        return value, check
    # Alphanumeric fields (document numbers): try swapping ambiguous characters.
    ambiguous = [i for i, c in enumerate(value) if c in _TO_DIGIT or c in _TO_ALPHA]
    if numeric or not ambiguous or len(ambiguous) > 8:
        return None
    for mask in itertools.product((False, True), repeat=len(ambiguous)):
        chars = list(value)
        for flip, i in zip(mask, ambiguous):
            if flip:
                c = chars[i]
                chars[i] = _TO_DIGIT.get(c) or _TO_ALPHA.get(c) or c
        candidate = "".join(chars)
        if check_digit(candidate) == check:
            return candidate, check
    return None


def _date(yymmdd: str, *, future: bool) -> date:
    if not yymmdd.isdigit():
        raise MRZError("date")
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    today = date.today()
    if future:  # expiry dates: 20xx unless clearly old
        year = 2000 + yy if yy < 70 else 1900 + yy
    else:  # birth dates are in the past
        year = 2000 + yy if 2000 + yy <= today.year else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        raise MRZError("date") from None


def _names(field_: str) -> tuple[str, str]:
    field_ = _alpha(field_)
    # OCR often reads trailing fillers "<<<<" as "K"s: drop short K-only tokens.
    parts = field_.split("<<", 1)
    last = parts[0].replace("<", " ").strip()
    given_raw = parts[1] if len(parts) > 1 else ""
    tokens = [t for t in given_raw.split("<") if t]
    # ... and blur leaves stray single letters in the filler ("VALI<C<<<").
    def filler_noise(tok: str) -> bool:
        return set(tok) <= {"K", "X"} and len(tok) <= 3

    while tokens and (filler_noise(tokens[-1]) or (len(tokens) > 1 and len(tokens[-1]) == 1)):
        tokens.pop()
    first = " ".join(tokens).strip()
    if not re.fullmatch(r"[A-Z ]{2,}", last) or (first and not re.fullmatch(r"[A-Z ]+", first)):
        raise MRZError("names")
    return last, first


def _sex(ch: str) -> str | None:
    return {"M": "male", "F": "female"}.get(ch)


def _personal_number(optional: str) -> str | None:
    digits = _digits(optional.replace("<", ""))
    m = re.search(r"\d{14}", digits)
    return m.group(0) if m else None


# ------------------------------------------------------------------ formats


def _fit(line: str, length: int) -> str:
    """Pad/trim to the exact length; OCR drops or adds trailing fillers."""
    return (line + "<" * length)[:length]


def parse_td3(l1: str, l2: str) -> MRZData:
    l1, l2 = _fit(l1, 44), _fit(l2, 44)
    doc = _repair_with_check(l2[0:9], l2[9], numeric=False)
    dob = _repair_with_check(l2[13:19], l2[19], numeric=True)
    exp = _repair_with_check(l2[21:27], l2[27], numeric=True)
    if not (doc and dob and exp):
        raise MRZError("check_digit")
    personal = l2[28:42]
    pcheck = l2[42]
    if personal.strip("<"):
        fixed = _repair_with_check(personal, pcheck, numeric=True) or _repair_with_check(
            personal, pcheck, numeric=False
        )
        if fixed is None:
            raise MRZError("check_digit")
        personal, pcheck = fixed
    composite = doc[0] + doc[1] + dob[0] + dob[1] + exp[0] + exp[1] + personal + pcheck
    if check_digit(composite) != _digits(l2[43]):
        raise MRZError("check_digit")
    last, first = _names(l1[5:44])
    return MRZData(
        format="TD3",
        document_code=_alpha(l1[0:2]).replace("<", ""),
        issuing_state=_alpha(l1[2:5]).replace("<", ""),
        document_number=doc[0].replace("<", ""),
        nationality=_alpha(l2[10:13]).replace("<", ""),
        birth_date=_date(dob[0], future=False),
        sex=_sex(l2[20]),
        expiry_date=_date(exp[0], future=True),
        last_name=last,
        first_name=first,
        personal_number=_personal_number(personal),
        lines=[l1, l2],
    )


def parse_td1(l1: str, l2: str, l3: str) -> MRZData:
    l1, l2, l3 = _fit(l1, 30), _fit(l2, 30), _fit(l3, 30)
    doc = _repair_with_check(l1[5:14], l1[14], numeric=False)
    dob = _repair_with_check(l2[0:6], l2[6], numeric=True)
    exp = _repair_with_check(l2[8:14], l2[14], numeric=True)
    if not (doc and dob and exp):
        raise MRZError("check_digit")
    optional1 = l1[15:30]
    optional2 = l2[18:29]
    # The optional fields carry no check digit of their own; the composite check
    # covers them. Uzbek ID cards keep the PINFL (digits) there, so also try a
    # digit-repaired version.
    for o1 in dict.fromkeys((optional1, _digits(optional1))):
        composite = doc[0] + doc[1] + o1 + dob[0] + dob[1] + exp[0] + exp[1] + optional2
        if check_digit(composite) == _digits(l2[29]):
            optional1 = o1
            break
    else:
        raise MRZError("check_digit")
    last, first = _names(l3)
    return MRZData(
        format="TD1",
        document_code=_alpha(l1[0:2]).replace("<", ""),
        issuing_state=_alpha(l1[2:5]).replace("<", ""),
        document_number=doc[0].replace("<", ""),
        nationality=_alpha(l2[15:18]).replace("<", ""),
        birth_date=_date(dob[0], future=False),
        sex=_sex(l2[7]),
        expiry_date=_date(exp[0], future=True),
        last_name=last,
        first_name=first,
        personal_number=_personal_number(optional1) or _personal_number(optional2),
        lines=[l1, l2, l3],
    )


def parse_td2(l1: str, l2: str) -> MRZData:
    l1, l2 = _fit(l1, 36), _fit(l2, 36)
    doc = _repair_with_check(l2[0:9], l2[9], numeric=False)
    dob = _repair_with_check(l2[13:19], l2[19], numeric=True)
    exp = _repair_with_check(l2[21:27], l2[27], numeric=True)
    if not (doc and dob and exp):
        raise MRZError("check_digit")
    composite = doc[0] + doc[1] + dob[0] + dob[1] + exp[0] + exp[1] + l2[28:35]
    if check_digit(composite) != _digits(l2[35]):
        raise MRZError("check_digit")
    last, first = _names(l1[5:36])
    return MRZData(
        format="TD2",
        document_code=_alpha(l1[0:2]).replace("<", ""),
        issuing_state=_alpha(l1[2:5]).replace("<", ""),
        document_number=doc[0].replace("<", ""),
        nationality=_alpha(l2[10:13]).replace("<", ""),
        birth_date=_date(dob[0], future=False),
        sex=_sex(l2[20]),
        expiry_date=_date(exp[0], future=True),
        last_name=last,
        first_name=first,
        personal_number=_personal_number(l2[28:35]),
        lines=[l1, l2],
    )


def find_mrz(lines: list[str]) -> MRZData:
    """Find and parse an MRZ among OCR text lines (top-to-bottom order).

    Raises MRZError with code "not_found" (nothing MRZ-like), "partial" (some
    MRZ lines missing) or "check_digit" (present but not read reliably,
    usually a blurry photo or glare).
    """
    cand = [normalize_line(x) for x in lines]
    cand = [c for c in cand if looks_like_mrz(c)]
    if not cand:
        raise MRZError("not_found")
    errors: list[MRZError] = []
    for i in range(len(cand)):
        window = cand[i : i + 3]
        attempts = []
        if (
            len(window) >= 2
            and 40 <= len(window[1]) <= 48
            and (40 <= len(window[0]) <= 48 or (window[0].startswith("P") and _is_names_line(window[0])))
        ):
            attempts.append(lambda w=window: parse_td3(w[0], w[1]))
        if (
            len(window) >= 3
            and all(26 <= len(x) <= 33 for x in window[:2])
            and (26 <= len(window[2]) <= 33 or _is_names_line(window[2]))
        ):
            attempts.append(lambda w=window: parse_td1(w[0], w[1], w[2]))
        if len(window) >= 2 and all(33 <= len(x) <= 39 for x in window[:2]):
            attempts.append(lambda w=window: parse_td2(w[0], w[1]))
        for attempt in attempts:
            try:
                return attempt()
            except MRZError as e:
                errors.append(e)
    # MRZ-like text was there but could not be read reliably ("check_digit"),
    # or only part of it is visible, e.g. the bottom of the page is cut off.
    raise MRZError("check_digit" if errors else "partial")
