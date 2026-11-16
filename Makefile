.PHONY: up down model migrate dev web test lint check-model eval-understand

up:            ## start Postgres and SearXNG
	docker compose up -d --wait

down:
	docker compose down

model:         ## build the local model (qwen3:8b with a 16K context window)
	ollama create flatjai-qwen3-8b -f deploy/ollama/Modelfile

migrate:       ## apply database migrations (Alembic)
	cd backend && uv run alembic upgrade head

dev: migrate   ## run the backend with reload on :8000 (interrupted runs resume on start)
	cd backend && uv run uvicorn flatjai.api:app --reload --port 8000

web:           ## run the UI on :3000 (needs `make up`, `make dev` and a model server)
	cd web && pnpm install --silent && pnpm dev

test:          ## unit, contract and agent-loop tests (no model, network or Postgres needed)
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check src tests && uv run ruff format --check src tests
	cd web && pnpm lint && pnpm exec tsc --noEmit

check-model:   ## a typed call to the active model returns a valid Profile
	cd backend && uv run python -m flatjai.check_model

eval-understand: ## Understand stage on the active model: briefs -> expected profile fields
	cd backend && uv run python ../eval/understand_check.py
