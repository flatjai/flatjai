.PHONY: up down otp-data otp-graph model migrate dev web test lint check-model eval-understand ablate \
	snapshot snapshot-import eval eval-score obs local tacc

local:         ## run the app here: services, API and web in one terminal (OFFLINE=1: snapshot only)
	./run.sh local $(if $(filter 1,$(OFFLINE)),--offline)

tacc:          ## the evaluation suite on Qwen 27B inside TACC, scored and loaded into the dashboard
	./run.sh tacc

up:            ## start Postgres, SearXNG and Grafana (and OpenTripPlanner once its graph is built)
	docker compose $(if $(wildcard infra/otp/data/graph.obj),--profile otp) up -d --wait

OTP_DATA = infra/otp/data
otp-data:      ## download the HK bus/minibus GTFS and the OSM extract, and write the MTR GTFS
	curl -sfL -o $(OTP_DATA)/gtfs.zip https://static.data.gov.hk/td/pt-headway-en/gtfs.zip
	curl -sfL -o $(OTP_DATA)/hong-kong.osm.pbf https://download.geofabrik.de/asia/china/hong-kong/hong-kong-latest.osm.pbf
	cd backend && uv run python ../scripts/build_mtr_gtfs.py

otp-graph: otp-data  ## build the OpenTripPlanner graph (~2 min, needs ~3.5 GB for Docker)
	docker run --rm -v "$(CURDIR)/$(OTP_DATA):/var/opentripplanner" -e JAVA_TOOL_OPTIONS=-Xmx3500m \
		opentripplanner/opentripplanner:2.10.0 --build --save

down:
	docker compose --profile otp down

model:         ## build the local model (qwen3:8b with a 16K context window)
	ollama create flatjai-qwen3-8b -f infra/ollama/Modelfile

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

SNAPSHOT ?= $(lastword $(sort $(wildcard data/snapshot-*.tar.zst)))
snapshot:      ## freeze every cached page, extraction and tool answer into data/snapshot-<date>.tar.zst
	scripts/snapshot.sh export

snapshot-import: ## load the frozen snapshot (SNAPSHOT=file, default: the newest) into Postgres
	scripts/snapshot.sh import $(SNAPSHOT)

SYSTEMS ?= b0 b1 flatjai
REPEAT ?= 1
eval:          ## the query suite on the frozen snapshot (offline) for each system, then the report
	@for s in $(SYSTEMS); do \
		(cd backend && FJ_OFFLINE=1 uv run python ../eval/run_suite.py --system $$s --repeat $(REPEAT) --tag offline) || exit 1; \
	done
	$(MAKE) eval-score

ABLATIONS ?= no_reflect no_dedup model_facts
ablate:        ## E2: the suite offline with one agent part off at a time, then the report with E1
	@for a in $(ABLATIONS); do \
		(cd backend && FJ_OFFLINE=1 uv run python ../eval/run_suite.py --system flatjai --ablate $$a --repeat $(REPEAT) --tag offline) || exit 1; \
	done
	$(MAKE) eval-score SYSTEMS="$(SYSTEMS) $(addprefix flatjai-,$(ABLATIONS))"

eval-score:    ## score the latest offline result of each system -> eval/results/report.md
	cd backend && uv run python ../eval/score.py $$(for s in $(SYSTEMS); do ls -t ../eval/results/*-$$s-offline.jsonl | head -1; done)

obs:           ## load TACC runs and eval scores for the Grafana dashboard -> http://localhost:3001
	cd backend && uv run python ../infra/grafana/load.py
