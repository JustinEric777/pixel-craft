# Repository Guidelines

## Project Structure & Module Organization

This local-first photo editor has a Python 3.11/FastAPI backend and React/TypeScript client. Backend responsibilities are separated across `api/` (HTTP), `core/` (domain rules), `services/` (use cases and ports), `storage/` (adapters), `image_ops/` (editing), and `ai/` (model runtimes and pipelines). Configuration lives in `configs/`; model and visual resources live in `models/` and `assets/`. Use `scripts/` for validation tools, `docs/` for engineering documentation, `tests/` for backend tests, and `frontend/src/` for UI code and colocated tests. Treat `data/` and `test_data/` as managed fixtures or generated evidence.

## Build, Test, and Development Commands

- `.tools/uv sync --group dev` installs the Python environment from `pyproject.toml` and `uv.lock`.
- `cd frontend && npm install` installs frontend dependencies.
- `./run-local.sh` starts the API on port 8000 and Vite on port 5173.
- `.venv/bin/ruff check ai api configs core services image_ops storage scripts tests` runs Python lint checks.
- `.venv/bin/pytest -q` runs the backend suite; add a path such as `tests/test_api.py` for focused work.
- `cd frontend && npm test` runs Vitest once; `npm run build` type-checks and creates the production bundle.

## Coding Style & Naming Conventions

Use four spaces and type hints in Python. Ruff targets Python 3.11 with a 100-character limit. Name modules, functions, and tests in `snake_case`; classes use `PascalCase`. In TypeScript, follow the existing two-space, double-quoted style: React components and files use `PascalCase`, while hooks begin with `use`. Keep domain logic out of HTTP handlers and use `services/ports/` interfaces across storage or model boundaries.

## Testing Guidelines

Write pytest files as `tests/test_<feature>.py` and functions as `test_<behavior>`. Frontend tests use Vitest and Testing Library with `*.test.ts` or `*.test.tsx`. Add regression tests beside the affected layer and use `tmp_path` rather than repository runtime directories. No numeric coverage threshold is configured; new behavior and failure paths should still be exercised. Before submitting, run the focused tests, then both full suites and the frontend build.

## Commit & Pull Request Guidelines

Git history is not included in this checkout. Use concise, imperative commit subjects (for example, `Fix stale preview replacement`) and keep unrelated changes separate. Pull requests should explain the user-visible effect, affected modules/configuration, and verification commands; link the relevant issue. Include before/after screenshots for UI changes and note model, asset, or fixture updates explicitly. Never commit `.env`, local weights, caches, generated diagnostics, uploads, or `frontend/node_modules/`; these are covered by `.gitignore`.
