#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/openclaw-armoriq}"
VENV_DIR="$ROOT_DIR/.venv"
PLUGIN_DIR="$ROOT_DIR/plugin"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"
WORKER_LOG="$LOG_DIR/worker.log"
GATEWAY_LOG="$LOG_DIR/gateway.log"
CONFIG_PATH="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
ARMORCLAW_DIST="$HOME/.openclaw/extensions/armorclaw/dist/index.js"

WORKER_STARTED=0
GATEWAY_STARTED=0
WORKER_PID=""
GATEWAY_PID=""

log() {
  printf '[run.sh] %s\n' "$*"
}

fail() {
  printf '[run.sh] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  local exit_code=$?

  if [[ "$GATEWAY_STARTED" -eq 1 && -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    log "Stopping gateway (pid=$GATEWAY_PID)"
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi

  if [[ "$WORKER_STARTED" -eq 1 && -n "$WORKER_PID" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
    log "Stopping worker (pid=$WORKER_PID)"
    kill "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi

  exit "$exit_code"
}

trap cleanup EXIT INT TERM

usage() {
  cat <<'EOF'
Usage: ./run.sh [tui-options...]

Sets up ClawShield, starts the Python worker and OpenClaw gateway if needed,
then opens the OpenClaw TUI in the current terminal.

Any arguments are passed directly to:
  node openclaw.mjs tui

Examples:
  ./run.sh
  ./run.sh --message "Fill the test form using my student profile"
  ./run.sh --session main
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

load_env() {
  [[ -f "$ROOT_DIR/.env" ]] || fail "Missing .env at $ROOT_DIR/.env"

  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a

  [[ -n "${OPENROUTER_API_KEY:-}" ]] || fail "OPENROUTER_API_KEY is not set in .env"
  [[ -n "${OPENROUTER_VISION_MODEL:-}" ]] || fail "OPENROUTER_VISION_MODEL is not set in .env"
  [[ -n "${ARMORIQ_API_KEY:-}" ]] || fail "ARMORIQ_API_KEY is not set in .env"
}

ensure_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creating Python virtual environment"
    python3 -m venv "$VENV_DIR"
  fi

  if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import fastapi, uvicorn, fitz, dotenv, openai, PIL  # noqa: F401
PY
  then
    log "Installing Python dependencies"
    "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"
  fi
}

ensure_plugin_build() {
  if [[ ! -d "$PLUGIN_DIR/node_modules" ]]; then
    log "Installing plugin dependencies"
    (cd "$PLUGIN_DIR" && npm install)
  fi

  log "Building plugin"
  (cd "$PLUGIN_DIR" && npm run build >/dev/null)
}

ensure_policy_file() {
  log "Writing ArmorClaw policy file"
  bash "$ROOT_DIR/scripts/init-policies.sh" >/dev/null
}

ensure_profile_alias() {
  if [[ ! -f "$ROOT_DIR/workspace/data/profile/student.json" && -f "$ROOT_DIR/workspace/data/profile/student_profile.json" ]]; then
    log "Creating sample student profile alias"
    cp "$ROOT_DIR/workspace/data/profile/student_profile.json" "$ROOT_DIR/workspace/data/profile/student.json"
  fi
}

ensure_openclaw_config() {
  log "Normalizing OpenClaw config"
  CLAWSHIELD_ROOT="$ROOT_DIR" CONFIG_PATH="$CONFIG_PATH" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["CLAWSHIELD_ROOT"])
config_path = Path(os.environ["CONFIG_PATH"]).expanduser()
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    with config_path.open() as f:
        cfg = json.load(f)
else:
    cfg = {}

cfg.setdefault("models", {})
cfg["models"].setdefault("providers", {})
cfg["models"]["providers"].setdefault("openrouter", {})
cfg["models"]["providers"]["openrouter"]["baseUrl"] = "https://openrouter.ai/api/v1"
cfg["models"]["providers"]["openrouter"]["apiKey"] = "${OPENROUTER_API_KEY}"
cfg["models"]["providers"]["openrouter"]["models"] = [
    {"id": "openrouter/hunter-alpha", "name": "Hunter Alpha"},
    {
        "id": "qwen/qwen3-vl-235b-a22b-instruct",
        "name": "Qwen3 VL 235B",
        "input": ["text", "image"],
    },
]

cfg.setdefault("agents", {})
cfg["agents"].setdefault("defaults", {})
cfg["agents"]["defaults"]["model"] = "openrouter/hunter-alpha"
cfg["agents"]["defaults"]["imageModel"] = "qwen/qwen3-vl-235b-a22b-instruct"
cfg["agents"]["defaults"]["workspace"] = str(root / "workspace")

cfg.setdefault("tools", {})
cfg["tools"]["allow"] = [
    "form_detect_fields",
    "form_extract_profile_data",
    "form_fill_pdf",
    "form_save_output",
    "form_transcribe_audio",
    "policy_update",
]

cfg.setdefault("gateway", {})
cfg["gateway"]["mode"] = "local"

cfg.setdefault("plugins", {})
cfg["plugins"]["allow"] = sorted(set(cfg["plugins"].get("allow", []) + ["clawshield", "armorclaw"]))
cfg["plugins"].setdefault("load", {})
paths = cfg["plugins"]["load"].get("paths", [])
plugin_path = str(root / "plugin")
if plugin_path not in paths:
    paths.append(plugin_path)
cfg["plugins"]["load"]["paths"] = paths

entries = cfg["plugins"].setdefault("entries", {})
entries["clawshield"] = {
    "enabled": True,
    "config": {
        "workerUrl": "http://127.0.0.1:8100",
        "workspacePath": str(root / "workspace"),
    },
}
entries["armorclaw"] = {
    "enabled": True,
    "config": {
        "enabled": True,
        "apiKey": "${ARMORIQ_API_KEY}",
        "policyStorePath": str(root / "workspace" / "armorclaw-policy.json"),
        "policyUpdateEnabled": True,
        "validitySeconds": 300,
    },
}

with config_path.open("w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
}

ensure_armorclaw_planner_patch() {
  [[ -f "$ARMORCLAW_DIST" ]] || return 0

  ARMORCLAW_DIST="$ARMORCLAW_DIST" python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["ARMORCLAW_DIST"]).expanduser()
text = path.read_text()

if "const parsed = JSON.parse(normalizedText);" in text:
    raise SystemExit(0)

needle = """    if (!text) {\n        throw new Error("Planner returned empty response");\n    }\n    try {\n        const parsed = JSON.parse(text);\n"""
replacement = """    if (!text) {\n        throw new Error("Planner returned empty response");\n    }\n    const normalizedText = (() => {\n        const trimmed = text.trim();\n        if (trimmed.startsWith("```")) {\n            const unfenced = trimmed.replace(/^```(?:json)?\\s*/i, "").replace(/\\s*```$/, "");\n            return unfenced.trim();\n        }\n        const jsonStart = trimmed.indexOf("{");\n        const jsonEnd = trimmed.lastIndexOf("}");\n        if (jsonStart !== -1 && jsonEnd !== -1 && jsonEnd > jsonStart) {\n            return trimmed.slice(jsonStart, jsonEnd + 1).trim();\n        }\n        return trimmed;\n    })();\n    try {\n        const parsed = JSON.parse(normalizedText);\n"""

if needle not in text:
    raise SystemExit(0)

path.write_text(text.replace(needle, replacement, 1))
PY
}

validate_openclaw_config() {
  log "Validating OpenClaw config"
  (cd "$OPENCLAW_DIR" && node openclaw.mjs config validate >/dev/null)
}

worker_ready() {
  curl -fsS "http://127.0.0.1:8100/health" >/dev/null 2>&1
}

gateway_ready() {
  python3 - <<'PY' >/dev/null 2>&1
import socket
sock = socket.socket()
sock.settimeout(1)
sock.connect(("127.0.0.1", 18789))
sock.close()
PY
}

wait_for() {
  local label="$1"
  local attempts="$2"
  local sleep_seconds="$3"
  local check_fn="$4"

  local i
  for ((i = 1; i <= attempts; i++)); do
    if "$check_fn"; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  return 1
}

start_worker() {
  if worker_ready; then
    log "Reusing existing worker on http://127.0.0.1:8100"
    return 0
  fi

  log "Starting worker"
  (
    cd "$ROOT_DIR"
    exec "$VENV_DIR/bin/python" -m uvicorn worker.server:app --host 127.0.0.1 --port 8100
  ) >>"$WORKER_LOG" 2>&1 &
  WORKER_PID=$!
  WORKER_STARTED=1

  wait_for "worker" 60 1 worker_ready || {
    tail -n 50 "$WORKER_LOG" >&2 || true
    fail "Worker did not become ready"
  }
}

start_gateway() {
  if gateway_ready; then
    log "Reusing existing gateway on ws://127.0.0.1:18789"
    return 0
  fi

  log "Starting gateway"
  (
    cd "$OPENCLAW_DIR"
    exec node openclaw.mjs gateway
  ) >>"$GATEWAY_LOG" 2>&1 &
  GATEWAY_PID=$!
  GATEWAY_STARTED=1

  wait_for "gateway" 90 1 gateway_ready || {
    tail -n 80 "$GATEWAY_LOG" >&2 || true
    fail "Gateway did not become ready"
  }
}

launch_tui() {
  log "Worker log: $WORKER_LOG"
  log "Gateway log: $GATEWAY_LOG"
  log "Opening OpenClaw TUI"
  (
    cd "$OPENCLAW_DIR"
    node openclaw.mjs tui "$@"
  )
}

main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi

  mkdir -p "$LOG_DIR"

  require_cmd python3
  require_cmd node
  require_cmd npm
  require_cmd curl

  [[ -d "$OPENCLAW_DIR" ]] || fail "OpenClaw repo not found at $OPENCLAW_DIR"

  load_env
  ensure_venv
  ensure_plugin_build
  ensure_policy_file
  ensure_profile_alias
  ensure_openclaw_config
  ensure_armorclaw_planner_patch
  validate_openclaw_config
  start_worker
  start_gateway
  launch_tui "$@"
}

main "$@"
