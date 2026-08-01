.PHONY: up up-prod down test format shell migrate revision downgrade update-deps update-data clean build-dev build-prod rmi-dev rmi-prod

up:
	docker compose up db bot

up-prod:
	docker compose up db bot_prod

down:
	docker compose down

test:
	uv sync --project ironforgedbot --extra dev
	uv run --project ironforgedbot python run_tests.py

format:
	docker compose run --rm --no-deps bot python -m black .

shell:
	docker compose run --rm bot /bin/sh

migrate:
	docker compose run --rm bot python -m alembic -c /install/lib/python3.14/site-packages/ironforgedcore/alembic.ini upgrade head

revision:
	docker compose run --rm bot python -m alembic -c /install/lib/python3.14/site-packages/ironforgedcore/alembic.ini revision --autogenerate -m "$(DESC)"

downgrade:
	docker compose run --rm bot python -m alembic -c /install/lib/python3.14/site-packages/ironforgedcore/alembic.ini downgrade -1

build-dev:
	docker compose build bot

build-prod:
	docker compose build bot_prod

rmi-dev:
	docker rmi ironforgedbot:dev

rmi-prod:
	docker rmi ironforgedbot:prod

update-deps:
	uv lock --directory ironforgedbot --upgrade
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
	$(MAKE) rmi-dev
	$(MAKE) rmi-prod
	@echo "Pruning unused Docker resources..."
	docker system prune -f --volumes
	@echo "Removing local build artifacts..."
	rm -rf dist/ build/ *.egg-info
	find . -type d -name "*.egg-info" \
		-not -path "./.venv/*" \
		-not -path "./.devenv/*" \
		-exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "__pycache__" \
		-not -path "./.venv/*" \
		-not -path "./.devenv/*" \
		-exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"
