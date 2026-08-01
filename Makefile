# Development tasks for coqui-ai-api.
#
# `make verify` is the gate: one command that checks the whole repository and
# exits non-zero on any problem. CI runs exactly this, so a green local run and
# a green CI run mean the same thing. Every other target here is a slice of it,
# for iterating.
#
# Requires uv (https://docs.astral.sh/uv/). Run `make install` once first.

UV ?= uv
RUN := $(UV) run
SOURCES := src tests

.PHONY: help install format format-check lint typecheck test audit verify smoke \
        dev-up dev-down dev-verify clean

help:
	@echo "make install       Install runtime + dev dependencies into .venv"
	@echo "make verify        The gate: format check, lint, types, tests, audit"
	@echo "make format        Rewrite imports and formatting in place"
	@echo "make format-check  Check formatting without rewriting"
	@echo "make lint          flake8, including mccabe complexity"
	@echo "make typecheck     mypy"
	@echo "make test          pytest with the coverage threshold"
	@echo "make audit         pip-audit against the Python Packaging Advisory Database"
	@echo "make smoke         Build the runtime image and check it serves /health"
	@echo "make dev-up        Start the development container"
	@echo "make dev-verify    Run the gate inside the development container"
	@echo "make dev-down      Stop the development container"
	@echo "make clean         Remove caches and build artefacts"

install:
	$(UV) sync --dev

# Rewrites files. Not part of `verify`, which must never mutate the tree.
format:
	$(RUN) isort $(SOURCES)
	$(RUN) black $(SOURCES)

format-check:
	$(RUN) isort --check-only --diff $(SOURCES)
	$(RUN) black --check --diff $(SOURCES)

lint:
	$(RUN) flake8 $(SOURCES)

typecheck:
	$(RUN) mypy

test:
	$(RUN) pytest --cov

audit:
	$(RUN) pip-audit

# The gate. Ordered cheapest-first so a fast failure comes back fast.
verify: format-check lint typecheck test audit
	@echo "verify: OK"

# Catches the class of break the unit tests structurally cannot: a Dockerfile or
# entrypoint that no longer works. Deliberately NOT part of `verify` and not run
# in CI: the base image is 16.9 GB, which is at or over the free disk a standard
# GitHub-hosted runner has. Run it on a machine that already has the base layer.
SMOKE_IMAGE ?= coqui-ai-api:smoke
SMOKE_PORT ?= 15000
smoke:
	docker build -t $(SMOKE_IMAGE) .
	@rm -rf .smoke-workspace && mkdir -p .smoke-workspace
	@printf 'model_name: tts_models/multilingual/multi-dataset/xtts_v2\ntts_to_file_params:\n  language: en\n' \
		> .smoke-workspace/config.yaml
	@docker rm -f coqui-ai-api-smoke >/dev/null 2>&1 || true
	@# COQUI_AI_API_START_WORKER=0: the model is not the thing under test here,
	@# and loading it would need weights and minutes.
	docker run --rm -d --name coqui-ai-api-smoke \
		-e COQUI_AI_API_START_WORKER=0 \
		-v "$(CURDIR)/.smoke-workspace:/workspace" \
		-p $(SMOKE_PORT):5000 $(SMOKE_IMAGE)
	@echo "waiting for /health ..."
	@for i in $$(seq 1 30); do \
		if curl -sf http://localhost:$(SMOKE_PORT)/health >/dev/null; then \
			echo "smoke: /health OK"; \
			curl -sf http://localhost:$(SMOKE_PORT)/openapi/openapi.json >/dev/null \
				&& echo "smoke: openapi spec OK"; \
			docker rm -f coqui-ai-api-smoke >/dev/null; \
			rm -rf .smoke-workspace; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "smoke: FAILED, container never answered /health" >&2; \
	docker logs coqui-ai-api-smoke 2>&1 | tail -30; \
	docker rm -f coqui-ai-api-smoke >/dev/null; \
	rm -rf .smoke-workspace; \
	exit 1

# --- Development container ---------------------------------------------------
# The sandbox autonomous agent runs happen in. It mounts this repository and
# nothing else: no host home directory, no SSH agent, no Docker socket.
DEV_COMPOSE := docker compose -f docker-compose.dev.yml

dev-up:
	$(DEV_COMPOSE) up -d --build
	$(DEV_COMPOSE) exec -T dev make install

dev-verify:
	$(DEV_COMPOSE) exec -T dev make verify

dev-down:
	$(DEV_COMPOSE) down

clean:
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
