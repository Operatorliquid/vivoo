.PHONY: install dev api build test

install:
	corepack pnpm install

dev:
	corepack pnpm --filter @courtvision/frontend dev

api:
	COURTVISION_CONFIG_FILE="$(CURDIR)/.courtvision/configuration.json" PYTHONPATH="$(CURDIR)/apps/api/src" python -m uvicorn main:app --host 0.0.0.0 --port 8000

build:
	corepack pnpm build

test:
	corepack pnpm test
