.PHONY: up down logs test test-api test-web lint format eval eval-llm sample-pdf

TEST_DB := postgresql://docchat:docchat@db:5432/docchat_test

up:            ## build and start db, api and web (http://localhost:8080)
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

test: test-api test-web

test-api:      ## unit + integration tests (integration uses the compose Postgres)
	docker compose up -d db
	docker compose run --rm --no-deps -e TEST_DATABASE_URL=$(TEST_DB) api pytest -q

test-web:
	cd web && npm ci --no-audit --no-fund && npm test && npm run typecheck

lint:
	docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."

format:
	docker compose run --rm --no-deps -v "$(PWD)/api:/app" api ruff format .

eval:          ## retrieval metrics on evals/golden_set.jsonl (no LLM cost)
	python3 evals/run_evals.py

eval-llm:      ## end-to-end answer + refusal accuracy (calls Gemini)
	python3 evals/run_evals.py --with-llm

sample-pdf:
	docker compose run --rm --no-deps -u root -v "$(PWD):/repo" api python /repo/scripts/make_sample_pdf.py
