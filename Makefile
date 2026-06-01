# lawagent — task runner. The important target is `make check`: it runs
# the same lint + types + tests CI runs, fast and offline. Run it before
# you push.
#
# Conventions:
#   - Python is driven through `uv` (never bare `python`/`pip`).
#   - Web (apps/web) is a separate npm project; its targets `cd` into it.
#   - Nothing here needs Postgres: the pgvector tests self-skip when the
#     DB / embedding keys are absent. Use `make db-up` to exercise them.

WEB := apps/web

.DEFAULT_GOAL := help
.PHONY: help check check-full py-lint py-test web-types web-lint web-build \
        docker-smoke fmt fmt-check install hooks db-up db-down clean

help: ## Show this help
	@grep -hE '^[a-z][a-zA-Z0-9_-]*:.*?## ' $(MAKEFILE_LIST) \
	  | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

## ---- the gate -------------------------------------------------------

# The gate: Python lint+tests, web lint+typecheck. Mirrors CI and is the
# whole feedback loop — fast (~5s), offline, no DB or API keys. Keep it
# green at all times. `web-build` is left out (slow; CI covers it).
check: py-lint py-test web-lint web-types ## Lint + types + tests (run before pushing)
	@echo "\033[32m✓ check passed\033[0m"

# The slow gate the pre-push hook runs: everything in `check` plus the two
# expensive signals CI also runs (next build + docker image). Catches them
# locally before the ~3-min CI round trip. `docker-smoke` self-skips when
# the Docker daemon isn't running.
check-full: check web-build docker-smoke ## check + web build + docker image (pre-push)
	@echo "\033[32m✓ check-full passed\033[0m"

## ---- python ---------------------------------------------------------

py-lint: ## Ruff lint over apps/ packages/ tests/
	uv run ruff check apps packages tests

py-test: ## Pytest (pgvector tests self-skip without a DB)
	uv run pytest -q

## ---- web (apps/web) -------------------------------------------------

web-types: ## TypeScript typecheck (tsc --noEmit)
	cd $(WEB) && npx tsc --noEmit

web-lint: ## ESLint over the web app
	cd $(WEB) && npm run lint

web-build: ## next build smoke (slower; mirrors CI). Needs no real creds.
	cd $(WEB) && AUTH_DISABLED=true SESSION_SECRET=make-only-placeholder npx next build

## ---- docker --------------------------------------------------------

docker-smoke: ## Build the deploy image (no push) — mirrors CI's docker job
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
	  docker build -t lawagent:prepush-smoke . ; \
	else \
	  echo "\033[33m• docker not running — skipping image smoke (CI will catch it)\033[0m" ; \
	fi

## ---- formatting (opt-in; NOT part of `check`) -----------------------

fmt: ## Apply ruff formatting (large diff — the tree predates it)
	uv run ruff format apps packages tests

fmt-check: ## Report files ruff format would change
	uv run ruff format --check apps packages tests

## ---- setup / infra --------------------------------------------------

install: hooks ## Install Python + web deps (uv sync --group local, npm ci) + git hooks
	uv sync --group local
	cd $(WEB) && npm ci

hooks: ## Activate the versioned git hooks in .githooks/ (pre-push gate)
	git config core.hooksPath .githooks
	@echo "git hooks active: $$(git config core.hooksPath)"

db-up: ## Start local Postgres + pgvector
	docker compose up -d db

db-down: ## Stop local Postgres
	docker compose stop db

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache $(WEB)/.next $(WEB)/tsconfig.tsbuildinfo
