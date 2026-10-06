# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/python -r requirements.txt

FROM python:3.13-slim AS final

LABEL org.opencontainers.image.source="https://github.com/elalemanyo/markitdown-sandbox" \
      org.opencontainers.image.description="Microsoft MarkItDown in a hardened, read-only container" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    PYTHONPATH=/python/lib/python3.13/site-packages \
    PATH="/python/bin:$PATH"

ARG UID=1000
ARG GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "${GID}" developer \
    && useradd -m -u "${UID}" -g "${GID}" -s /usr/sbin/nologin developer

COPY --from=builder /python /python
COPY app /app

WORKDIR /workspace
USER developer

# Web UI port, used by `serve`.
EXPOSE 8000

ENTRYPOINT ["python", "/app/main.py"]
