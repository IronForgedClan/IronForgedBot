# builder: compile all prod wheels
FROM python:3.13-alpine AS builder

RUN apk add --no-cache \
    mariadb-dev \
    gcc \
    musl-dev \
    pkgconf \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    libffi-dev

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
 && find /install -name '__pycache__' -exec rm -rf {} + 2>/dev/null; \
    find /install -name '*.dist-info' -exec rm -rf {} + 2>/dev/null; \
    find /install -name '*.egg-info' -exec rm -rf {} + 2>/dev/null; \
    rm -rf /install/lib/python3.13/site-packages/pip

# runner: clean Alpine + mariadb-connector-c + botuser, shared by prod images
FROM python:3.13-alpine AS runner

RUN apk add --no-cache mariadb-connector-c

RUN adduser -D botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

USER botuser

# bot-prod: bot + core only
FROM runner AS bot-prod

COPY --from=builder /install /usr/local
COPY --chown=botuser:botuser main.py ./
COPY --chown=botuser:botuser ironforgedbot ./ironforgedbot

CMD ["python", "main.py"]

# api-prod: api + core only
FROM runner AS api-prod

COPY --from=builder /install /usr/local
COPY --chown=botuser:botuser api ./api

CMD ["python", "-m", "api.main"]

# dev: builder + dev dependencies + file watcher + full copy for self-contained dev
FROM builder AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

RUN adduser -D botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=botuser:botuser . .

USER botuser

CMD ["watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]

# api-dev: dev deps + uvicorn auto-reload for the API service
FROM dev AS api-dev

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
