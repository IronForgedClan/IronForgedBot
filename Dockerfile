FROM python:3-alpine

RUN adduser -D bot
USER bot

WORKDIR ~

COPY --chown=bot:bot requirements.txt .
RUN pip install -r requirements.txt --no-warn-script-location

COPY --chown=bot:bot . .

CMD [ "python3", "main.py" ]
