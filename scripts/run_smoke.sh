#!/usr/bin/env bash
# =============================================================================
# run_smoke.sh — Quick connectivity and sanity check
# =============================================================================
#
# Runs 1 virtual user for 30 seconds to verify the target is reachable and
# all endpoints return expected status codes before a full load test.
#
# USAGE
#   ./run_smoke.sh [-e ENV] [-H HOST] [-O PORT] [-S PROTOCOL]
#
# EXAMPLES
#   ./run_smoke.sh                        # smoke QA (default)
#   ./run_smoke.sh -e staging             # smoke staging
#   ./run_smoke.sh -H 10.0.0.50 -O 8080  # override host
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_NAME="qa"
HOST_OVERRIDE=""
PORT_OVERRIDE=""
PROTOCOL_OVERRIDE=""

while getopts "e:H:O:S:h" opt; do
  case $opt in
    e) ENV_NAME="$OPTARG" ;;
    H) HOST_OVERRIDE="$OPTARG" ;;
    O) PORT_OVERRIDE="$OPTARG" ;;
    S) PROTOCOL_OVERRIDE="$OPTARG" ;;
    h) echo "Usage: $0 [-e ENV] [-H HOST] [-O PORT] [-S PROTOCOL]"; exit 0 ;;
  esac
done

echo "[SMOKE] Running 1-user / 30s sanity check on environment: $(echo "$ENV_NAME" | tr '[:lower:]' '[:upper:]')"

EXTRA_ARGS=()
[[ -n "$HOST_OVERRIDE" ]]     && EXTRA_ARGS+=(-H "$HOST_OVERRIDE")
[[ -n "$PORT_OVERRIDE" ]]     && EXTRA_ARGS+=(-O "$PORT_OVERRIDE")
[[ -n "$PROTOCOL_OVERRIDE" ]] && EXTRA_ARGS+=(-S "$PROTOCOL_OVERRIDE")

bash "$SCRIPT_DIR/run_test.sh" \
  -e "$ENV_NAME" \
  -u 1 \
  -r 1 \
  -d 30 \
  "${EXTRA_ARGS[@]}"
