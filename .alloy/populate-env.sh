#!/usr/bin/env bash
#
# Idempotent environment file setup for the Grocery Agent app.
#
# - Safe to run multiple times.
# - Reads values from the current process environment first.
# - Only fills in local-dev-safe defaults / placeholders for values that are
#   required to let the app boot when they are missing or blank.
# - Never overwrites a real user-provided value.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

touch "$ENV_FILE"

# get_env_value KEY -> echoes the current value of KEY from .env (without key=)
get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d'=' -f2- || true
}

# set_env_if_blank KEY VALUE
# Writes KEY=VALUE only if KEY is missing or its current value is blank/placeholder.
set_env_if_blank() {
  local key="$1"
  local value="$2"
  local current
  current="$(get_env_value "$key")"

  if [ -n "$current" ] && [ "$current" != "changeme" ] && [ "$current" != "your_gemini_api_key_here" ]; then
    # Real user-provided value already present; leave it untouched.
    return 0
  fi

  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # Replace existing (blank/placeholder) line.
    local tmp
    tmp="$(mktemp)"
    grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
    mv "$tmp" "$ENV_FILE"
  fi
  printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

# GOOGLE_API_KEY is required to instantiate the Gemini LLM client at startup.
# Image OCR and LLM-backed multi-word search require a real key to function,
# but the rest of the app (search, basket, recommendations) boots and renders
# fine with a placeholder. Prefer a real key from the environment if present.
GOOGLE_API_KEY_VALUE="${GOOGLE_API_KEY:-${GEMINI_API_KEY:-}}"
if [ -z "$GOOGLE_API_KEY_VALUE" ]; then
  # Local-dev placeholder so the client can be constructed without a real key.
  GOOGLE_API_KEY_VALUE="local-dev-placeholder-key"
fi
set_env_if_blank "GOOGLE_API_KEY" "$GOOGLE_API_KEY_VALUE"

# Flask configuration for running inside the sandbox behind the Alloy proxy.
set_env_if_blank "FLASK_APP" "app.py"
set_env_if_blank "FLASK_RUN_HOST" "0.0.0.0"
set_env_if_blank "FLASK_RUN_PORT" "5000"

# PostgreSQL configuration. These are local-dev defaults; a real deployment can
# override any of them by exporting the values before running this script.
set_env_if_blank "POSTGRES_USER" "${POSTGRES_USER:-grocery}"
set_env_if_blank "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-grocery}"
set_env_if_blank "POSTGRES_DB" "${POSTGRES_DB:-grocery}"
set_env_if_blank "DATABASE_URL" \
  "${DATABASE_URL:-postgresql+psycopg://grocery:grocery@localhost:5432/grocery}"

# Expose the Alloy runtime flag to the app if anything wants to branch on it.
set_env_if_blank "IS_ALLOY" "${IS_ALLOY:-false}"

echo "Environment file prepared at $ENV_FILE"
