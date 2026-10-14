#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  trap - EXIT INT TERM

  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  [[ -n "$BACKEND_PID" ]] && wait "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

if [[ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]]; then
  echo "后端依赖未安装，请先运行："
  echo "  cd $ROOT_DIR && .tools/uv sync --group dev"
  exit 1
fi

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
  echo "前端依赖未安装，请先运行："
  echo "  cd $ROOT_DIR/frontend && npm install"
  exit 1
fi

echo "正在启动后端：http://127.0.0.1:8000"
(
  cd "$ROOT_DIR" || exit 1
  exec .venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
) &
BACKEND_PID=$!

echo "正在启动前端：http://127.0.0.1:5173"
(
  cd "$ROOT_DIR/frontend" || exit 1
  exec npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

echo "按 Ctrl+C 停止前后端服务。"

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  wait "$BACKEND_PID"
  exit $?
fi

wait "$FRONTEND_PID"
