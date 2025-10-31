.PHONY: up down test format shell migrate revision downgrade update-deps update-data clean

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

update-deps:
	docker compose run --rm bot /home/botuser/.local/bin/pip-compile --upgrade requirements.in
	docker compose build bot

update-data:
	git submodule update --remote data
	@echo "Data submodule updated to latest commit"

clean:
	@echo "Stopping containers..."
	docker compose down
	@echo "Removing project containers..."
	docker compose rm -f
	@echo "Removing project images..."
	docker images -q ironforgedbot* | xargs -r docker rmi -f
	@echo "Pruning unused Docker resources..."
	docker system prune -f --volumes
	@echo "Cleanup complete!"

