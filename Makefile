SHELL := /bin/bash
COMPOSE := docker compose
PYTHON := python3
.PHONY: setup dev migrate seed-demo test test-e2e check reset-demo stop local-setup local-dev demo-access
setup:
	@$(PYTHON) -c 'import sys; assert sys.version_info >= (3,12), "Richiesto Python 3.12+"'
	@docker info >/dev/null
	@docker compose version
	@mkdir -p work
	@$(PYTHON) scripts/setup.py
	$(COMPOSE) build
	@echo 'Setup completato. Ora: make dev && make seed-demo'
dev:
	$(COMPOSE) up -d db redis migrate api worker scheduler frontend
	@echo 'Demo: http://localhost:8081 — attendere healthcheck, poi make seed-demo'
migrate:
	$(COMPOSE) run --rm migrate
seed-demo:
	$(COMPOSE) run --rm --user "$$(id -u):$$(id -g)" seed
	@echo 'Account demo: make demo-access'
demo-access:
	@$(PYTHON) scripts/access.py
stop:
	$(COMPOSE) stop
test:
	$(COMPOSE) run --rm -e MIGRATION_DATABASE_URL=postgresql+psycopg://tavolo_owner:local-demo-owner@db:5432/tavolo_demo_test migrate
	$(COMPOSE) run --rm -v "$(CURDIR)/scripts:/scripts:ro" -e TAVOLO_TEST_DATABASE_URL=postgresql+psycopg://tavolo_app:local-demo-app@db:5432/tavolo_demo_test -e TAVOLO_TEST_OWNER_URL=postgresql+psycopg://tavolo_owner:local-demo-owner@db:5432/tavolo_demo_test api pytest -q
	$(COMPOSE) run --rm frontend-check
# Browser runs on the host against loopback ingress, never against a remote restaurant.
test-e2e:
	cd frontend && npm ci --cache ../work/npm
	cd frontend && npx playwright install chromium
	cd frontend && TAVOLO_UI_URL=http://localhost:8081 npm run test:e2e
check:
	$(COMPOSE) config --quiet
	$(COMPOSE) build
	$(MAKE) test
reset-demo:
	$(PYTHON) scripts/reset_demo.py
local-setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r backend/requirements.lock
	$(PYTHON) scripts/setup.py
	cd frontend && npm ci --cache ../work/npm
local-dev:
	@echo 'Avvia in terminali separati: vedi README sezione sviluppo locale.'
