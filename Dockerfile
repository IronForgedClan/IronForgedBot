# builder: install prod wheels into the default location (/usr/local)
FROM python:3.13-alpine AS builder

RUN apk add --no-cache \
    mariadb-dev \
    gcc \
    musl-dev \
    pkgconf \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    libffi-dev \
    git

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

COPY ironforgedbot ./ironforgedbot
RUN uv pip install --system ./ironforgedbot \
 && uv pip install --system "./ironforgedbot[dev]" \
 && find /usr/local -name '__pycache__' -exec rm -rf {} + 2>/dev/null; \
    find /usr/local -name '*.dist-info' -exec rm -rf {} + 2>/dev/null; \
    find /usr/local -name '*.egg-info' -exec rm -rf {} + 2>/dev/null; \
    rm -rf /usr/local/lib/python3.13/site-packages/pip

# runner: clean Alpine + mariadb-connector-c + botuser, shared by prod images
FROM python:3.13-alpine AS runner

RUN apk add --no-cache mariadb-connector-c

RUN adduser -D botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

USER botuser

# bot-prod: bot only
FROM runner AS bot-prod

COPY --from=builder /usr/local /usr/local
COPY --chown=botuser:botuser main.py ./
COPY --chown=botuser:botuser ironforgedbot ./ironforgedbot

CMD ["python", "main.py"]

# dev: builder + dev dependencies + file watcher + full copy for self-contained dev
FROM builder AS dev

RUN adduser -D botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

COPY --from=builder /usr/local /usr/local
COPY --chown=botuser:botuser . .

USER botuser

CMD ["watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]
