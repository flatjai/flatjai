.PHONY: up down dev test check-model

up:            ## start Postgres
	docker compose up -d --wait

down:
	docker compose down

dev:           ## run the backend with reload on :8000
	cd backend && uv run uvicorn flatjai.api:app --reload --port 8000

test:          ## unit tests (no model, no network)
	cd backend && uv run pytest -q

check-model:   ## M0 check: a typed call to the active model returns a valid Profile
	cd backend && uv run python -m flatjai.check_model
