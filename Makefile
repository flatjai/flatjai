.PHONY: up down otp-data otp-graph model migrate dev web test lint check-model eval-understand

up:            ## start Postgres and SearXNG (and OpenTripPlanner once its graph is built)
	docker compose $(if $(wildcard deploy/otp/data/graph.obj),--profile otp) up -d --wait

OTP_DATA = deploy/otp/data
otp-data:      ## download the HK bus/minibus GTFS and the OSM extract, and write the MTR GTFS
	curl -sfL -o $(OTP_DATA)/gtfs.zip https://static.data.gov.hk/td/pt-headway-en/gtfs.zip
	curl -sfL -o $(OTP_DATA)/hong-kong.osm.pbf https://download.geofabrik.de/asia/china/hong-kong-latest.osm.pbf
	cd backend && uv run python scripts/build_mtr_gtfs.py

otp-graph: otp-data  ## build the OpenTripPlanner graph (~2 min, needs ~3.5 GB for Docker)
	docker run --rm -v "$(CURDIR)/$(OTP_DATA):/var/opentripplanner" -e JAVA_TOOL_OPTIONS=-Xmx3500m \
		opentripplanner/opentripplanner:2.10.0 --build --save

down:
	docker compose --profile otp down

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
