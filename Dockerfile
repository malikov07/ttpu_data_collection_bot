# --- 1. Build the staff web panel ---------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. Python app (bot + web API + backups) ------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
# Runtime libraries used by OpenCV / ONNX Runtime; pg_dump for backups
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# rapidocr pulls in the desktop OpenCV build, which needs X11 libraries. Both
# builds share the cv2 module, so keep only the headless one.
RUN pip install -r requirements.txt \
    && v=$(pip show opencv-python-headless | awk '/^Version:/{print $2}') \
    && pip uninstall -y opencv-python opencv-python-headless \
    && pip install --no-deps "opencv-python-headless==$v" \
    && python -c "import cv2; cv2.FaceDetectorYN; print('OpenCV', cv2.__version__)"

COPY app ./app
COPY alembic.ini ./
COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/data/uploads /app/data/telegram-files /app/backups \
    && chown -R bot:bot /app
USER bot

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')"
CMD ["python", "-m", "app"]
