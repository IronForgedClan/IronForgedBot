.PHONY: test shell migrate revision downgrade

test:
	docker compose run --rm bot python run_tests.py

shell:
	docker compose run --rm bot /bin/bash

migrate:
	docker compose run --rm bot /home/botuser/.local/bin/alembic upgrade head

revision:
	docker compose run --rm bot /home/botuser/.local/bin/alembic revision -m "$(DESC)"

downgrade:
	docker compose run --rm bot /home/botuser/.local/bin/alembic downgrade -1

