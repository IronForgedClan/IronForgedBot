.PHONY: up down test format shell migrate revision downgrade

up:
	docker compose up

down:
	docker compose down

test:
	docker compose run --rm bot python run_tests.py

format:
	docker compose run --rm bot python -m black .

shell:
	docker compose run --rm bot /bin/bash

migrate:
	docker compose run --rm bot /home/botuser/.local/bin/alembic upgrade head

revision:
	docker compose run --rm bot /home/botuser/.local/bin/alembic revision --autogenerate -m "$(DESC)"

downgrade:
	docker compose run --rm bot /home/botuser/.local/bin/alembic downgrade -1

