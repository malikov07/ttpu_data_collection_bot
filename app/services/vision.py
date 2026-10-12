"""On-server image analysis: passport OCR and 3x4 photo checks.

Everything runs locally with bundled models (RapidOCR / PaddleOCR ONNX models
and OpenCV's YuNet face detector). No image or extracted data ever leaves
the server: there are no network calls in this module.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import cv2
import numpy as np

from app.services.mrz import MRZData, MRZError, find_mrz, looks_like_mrz, normalize_line
from app.services.validators import pretty_name

log = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FACE_MODEL = ASSETS / "face_detection_yunet_2023mar.onnx"

# Shorter side of a document image. Downloaded e-ID images (e.g. from my.gov.uz)
# are small but sharp: they are upscaled for OCR, and the check digits still
# catch any misread, so only truly tiny images are refused.
MIN_DOC_SIDE = 250  # px
OCR_MIN_SIDE = 1000  # px: smaller documents are upscaled to this before OCR
MIN_PHOTO_SIDE = 300  # px, shorter side of a 3x4 photo
MAX_SIDE = 2000  # larger images are downscaled before OCR (speed)
# Documents of these states print the patronymic (in Latin letters on Uzbek ones).
# Elsewhere a name ending in "-ich" (e.g. Dietrich) must not be taken for one.
PATRONYMIC_STATES = {"UZB", "RUS", "KAZ", "KGZ", "TJK", "TKM", "AZE", "BLR", "UKR"}
BLUR_LIMIT = 25.0  # variance of the Laplacian below this = blurry
# OCR confidence required on every MRZ line. The name line has no check digit,
# so a low-confidence read could add or drop letters unnoticed.
MRZ_MIN_SCORE = 0.95
# The patronymic has no check digit at all. Glare on the laminate makes OCR swap
# letters, so a line read with less confidence is not suggested: the student
# types it instead.
PATRONYMIC_MIN_SCORE = 0.93

# One worker: OCR is CPU-heavy (onnxruntime already uses several cores) and
# serialising keeps memory predictable when many students upload at once.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision")
_engine_lock = threading.Lock()
_ocr_engine = None
_face_detector = None


# ------------------------------------------------------------------ helpers


def decode(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None and img.size else None


def _downscale(img: np.ndarray, max_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return img
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _for_ocr(img: np.ndarray) -> np.ndarray:
    """Downscale big photos; upscale small images so the MRZ letters are big enough."""
    img = _downscale(img, MAX_SIDE)
    h, w = img.shape[:2]
    factor = min(OCR_MIN_SIDE / min(h, w), MAX_SIDE / max(h, w))
    if factor > 1.05:
        img = cv2.resize(img, (round(w * factor), round(h * factor)), interpolation=cv2.INTER_CUBIC)
    return img


def sharpness(img: np.ndarray) -> float:
    """Variance of the Laplacian on a normalised size: low = blurry."""
    gray = cv2.cvtColor(_downscale(img, 1000), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _ocr():
    global _ocr_engine
    with _engine_lock:
        if _ocr_engine is None:
            from rapidocr import RapidOCR

            logging.getLogger("RapidOCR").setLevel(logging.WARNING)
            _ocr_engine = RapidOCR()
        return _ocr_engine


def _faces():
    global _face_detector
    with _engine_lock:
        if _face_detector is None:
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)  # hide a harmless warning
            _face_detector = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), 0.75, 0.3, 50)
        return _face_detector


def _ocr_lines(img: np.ndarray) -> list[tuple[str, float]]:
    """(text, confidence) of every text line, top to bottom."""
    result = _ocr()(img)
    if result is None or result.txts is None:
        return []
    boxes = result.boxes if result.boxes is not None else [None] * len(result.txts)
    items = []
    for text, score, box in zip(result.txts, result.scores, boxes):
        top = float(np.min(np.asarray(box)[:, 1])) if box is not None else 0.0
        left = float(np.min(np.asarray(box)[:, 0])) if box is not None else 0.0
        items.append((top, left, text, float(score)))
    items.sort()
    return [(text, score) for _, _, text, score in items]


def _mrz_confident(lines: list[tuple[str, float]]) -> bool:
    scores = [score for text, score in lines if looks_like_mrz(normalize_line(text))]
    return bool(scores) and min(scores) >= MRZ_MIN_SCORE


def detect_faces(img: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    small = _downscale(img, 640)
    h, w = small.shape[:2]
    detector = _faces()
    detector.setInputSize((w, h))
    _, faces = detector.detect(small)
    if faces is None:
        return []
    scale = img.shape[1] / w
    return [(int(f[0] * scale), int(f[1] * scale), int(f[2] * scale), int(f[3] * scale), float(f[14])) for f in faces]


# ------------------------------------------------------------------ documents

_PATRONYMIC = [
    re.compile(r"\b([A-Z][A-Z'ʻ`’]{2,}(?:OVICH|EVICH|YEVICH|OVNA|EVNA|YEVNA|ICH|VNA))\b"),
    re.compile(r"\b([A-Z][A-Z'ʻ`’]{2,})\s+(O['ʻ`’]?G['ʻ`’]?LI|QIZI)\b"),
]
_NOT_NAMES = {"PATRONYMIC"}


def guess_patronymic(lines: list[tuple[str, float]], *, not_names: set[str] = frozenset()) -> str | None:
    """Suggest the patronymic from the printed text (it is not in the MRZ).

    None when it can't be found or wasn't read confidently. ``not_names``: the
    surname and given names, which are printed too and are never the patronymic.
    """
    for line, score in lines:
        text = line.upper()
        for pattern in _PATRONYMIC:
            m = pattern.search(text)
            if m and m.group(1) not in _NOT_NAMES | not_names:
                if score < PATRONYMIC_MIN_SCORE:
                    return None
                return pretty_name(" ".join(g for g in m.groups() if g))
    return None


@dataclass(slots=True)
class DocumentResult:
    error: str | None  # None when ok; see ERRORS below
    mrz: MRZData | None = None
    patronymic: str | None = None


def prints_patronymic(issuing_state: str | None) -> bool:
    return issuing_state in PATRONYMIC_STATES


# not_image, too_small, blurry, not_found, partial, unreadable, expired, visa
def _read_document(data: bytes, today: date) -> DocumentResult:
    img = decode(data)
    if img is None:
        return DocumentResult("not_image")
    if min(img.shape[:2]) < MIN_DOC_SIDE:
        return DocumentResult("too_small")
    blurry = sharpness(img) < BLUR_LIMIT  # on the image as sent: upscaling softens it
    img = _for_ocr(img)

    # Phone photos are often sideways: try every orientation. Keep the most
    # informative failure (an MRZ that was seen beats "nothing found").
    priority = {"not_found": 0, "partial": 1, "check_digit": 2}
    best_error = "not_found"
    for rotation in (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180):
        view = img if rotation is None else cv2.rotate(img, rotation)
        lines = _ocr_lines(view)
        texts = [text for text, _ in lines]
        try:
            mrz = find_mrz(texts)
        except MRZError as e:
            if priority[str(e)] > priority[best_error]:
                best_error = str(e)
            continue
        if not _mrz_confident(lines):
            best_error = "check_digit"
            continue
        if mrz.document_code.startswith("V"):  # a visa sticker, not the passport page
            return DocumentResult("visa", mrz=mrz)
        if mrz.expiry_date < today:
            return DocumentResult("expired", mrz=mrz)
        patronymic = None
        if prints_patronymic(mrz.issuing_state):
            patronymic = guess_patronymic(lines, not_names=set(f"{mrz.last_name} {mrz.first_name}".split()))
        return DocumentResult(None, mrz=mrz, patronymic=patronymic)

    if best_error == "check_digit":
        return DocumentResult("blurry" if blurry else "unreadable")
    if best_error == "not_found" and blurry:
        return DocumentResult("blurry")
    return DocumentResult(best_error)


async def read_document(data: bytes) -> DocumentResult:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _read_document, data, date.today())


# ------------------------------------------------------------------ photos


def _check_portrait(data: bytes) -> str | None:
    """None if this is a usable 3x4 portrait, otherwise an error code."""
    img = decode(data)
    if img is None:
        return "not_image"
    h, w = img.shape[:2]
    if min(h, w) < MIN_PHOTO_SIDE:
        return "too_small"
    ratio = h / w
    if not 1.1 <= ratio <= 1.7:
        return "not_portrait"
    if sharpness(img) < BLUR_LIMIT:
        return "blurry"
    faces = detect_faces(img)
    if not faces:
        return "no_face"
    if len(faces) > 1:
        return "many_faces"
    x, y, fw, fh, _ = faces[0]
    if fw < 0.25 * w:
        return "face_too_small"
    return None


def _check_id_front(data: bytes) -> tuple[str | None, str | None]:
    """The front side of an ID card: a readable image with the holder's photo.

    Returns (error, patronymic suggestion): Uzbek ID cards print the
    patronymic only on the front.
    """
    img = decode(data)
    if img is None:
        return "not_image", None
    if min(img.shape[:2]) < MIN_DOC_SIDE:
        return "too_small", None
    if sharpness(img) < BLUR_LIMIT:
        return "blurry", None
    img = _for_ocr(img)
    if not detect_faces(img):
        return "no_face", None
    return None, guess_patronymic(_ocr_lines(img))


async def check_portrait(data: bytes) -> str | None:
    return await asyncio.get_running_loop().run_in_executor(_executor, _check_portrait, data)


async def check_id_front(data: bytes) -> tuple[str | None, str | None]:
    return await asyncio.get_running_loop().run_in_executor(_executor, _check_id_front, data)


def warm_up() -> None:
    """Load the models at startup instead of on the first student's upload."""
    _ocr()
    _faces()
