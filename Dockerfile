FROM python:3.13-slim AS base

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    gcc \
    libpq-dev \
 && pip install --no-cache-dir --upgrade pip \
 && apt-get purge -y gcc \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m botuser

WORKDIR /app
COPY --chown=botuser:botuser . .

USER botuser

RUN pip install --no-cache-dir -r requirements.txt

FROM base AS dev
RUN pip install --no-cache-dir 'watchdog[watchmedo]'
CMD ["/home/botuser/.local/bin/watchmedo", "auto-restart", "--wait=2", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]

FROM base AS prod
CMD ["python", "main.py"]

