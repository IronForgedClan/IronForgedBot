.PHONY: up up-prod up-full down test format shell migrate revision downgrade update-deps update-data clean build-dev build-prod rmi-dev rmi-prod api-up api-down api-logs api-shell api-manage

up:
	docker compose up db bot

up-prod:
	docker compose up db bot_prod

up-full:
	docker compose --profile full up db bot_prod api

down:
	docker compose down

test:
	docker compose run --rm bot python run_tests.py

format:
	docker compose run --rm bot python -m black .

shell:
	docker compose run --rm bot /bin/sh

migrate:
	docker compose run --rm bot python -m alembic -c ironforgedcore/alembic.ini upgrade head

revision:
	docker compose run --rm bot python -m alembic -c ironforgedcore/alembic.ini revision --autogenerate -m "$(DESC)"

downgrade:
	docker compose run --rm bot python -m alembic -c ironforgedcore/alembic.ini downgrade -1

build-dev:
	docker compose build bot

build-prod:
	docker compose build bot_prod

rmi-dev:
	docker rmi ironforgedbot:dev

rmi-prod:
	docker rmi ironforgedbot:prod

update-deps:
	docker compose run --rm bot python -m piptools compile --upgrade requirements.in
	docker compose run --rm bot python -m piptools compile --upgrade requirements-dev.in -o requirements-dev.txt
	docker compose build bot

update-data:
	git submodule update --remote data
	@echo "Data submodule updated to latest commit"

api-up:
	docker compose up -d api

api-down:
	docker compose stop api

api-logs:
	docker compose logs -f api

api-shell:
	docker compose exec api /bin/sh

api-manage:
	docker compose run --rm bot python scripts/manage_api_consumers.py interactive

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
	@echo "Cleanup complete!"

