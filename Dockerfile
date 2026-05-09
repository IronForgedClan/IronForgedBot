# builder: compile all prod wheels (needs gcc + mysql headers)
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

# prod: clean Alpine image, runtime-only MySQL lib, no compilers
FROM python:3.13-alpine AS prod

RUN apk add --no-cache mariadb-connector-c

RUN adduser -D botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=botuser:botuser . .

USER botuser
CMD ["python", "main.py"]

# dev: builder + dev dependencies + file watcher
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
