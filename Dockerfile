# builder: compile all prod wheels (needs gcc + mysql headers)
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    gcc \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# prod: clean image, runtime-only MySQL lib, no compilers
FROM python:3.13-slim AS prod

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=botuser:botuser . .

USER botuser
CMD ["python", "main.py"]

# dev: builder + dev dependencies + file watcher
FROM builder AS dev

RUN useradd -m botuser
RUN mkdir /app && chown botuser:botuser /app
WORKDIR /app

COPY --chown=botuser:botuser . .

USER botuser

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN pip install --no-cache-dir -r requirements.txt

CMD ["/home/botuser/.local/bin/watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]
