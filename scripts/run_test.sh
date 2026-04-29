#!/usr/bin/env bash
# =============================================================================
# run_test.sh — AEP Performance Test Runner
# =============================================================================
#
# Executes a JMeter test plan against a target environment, supports multiple
# load profiles, repeated runs, and optional parallel execution.
#
# USAGE
#   ./run_test.sh [OPTIONS]
#
# OPTIONS
#   -e  ENV           Environment preset: qa | staging | prod  (default: qa)
#   -p  PLAN          Test plan filename in test-plans/
#                     (default: AEP_ECommerce_Performance_TestPlan.jmx)
#   -u  USERS         Virtual user count: 5 | 10 | 15 | <any int>  (default: 5)
#   -r  RAMP          Ramp-up period in seconds                     (default: env preset)
#   -d  DURATION      Test duration in seconds                      (default: env preset)
#   -i  ITERATIONS    Number of sequential test runs                (default: 1)
#   -P               Run iterations in PARALLEL instead of sequentially
#   -H  HOST          Override host (ignores env preset)
#   -O  PORT          Override port (ignores env preset)
#   -S  PROTOCOL      Override protocol http|https
#   -h               Show this help and exit
#
# EXAMPLES
#   # Smoke check on QA with 5 users
#   ./run_test.sh -e qa -u 5 -d 60
#
#   # Full load run: 10 users, 5-minute soak, 3 sequential iterations
#   ./run_test.sh -e qa -u 10 -d 300 -i 3
#
#   # Stress test: 15 users, 3 parallel runs
#   ./run_test.sh -e qa -u 15 -d 300 -i 3 -P
#
#   # Override host at runtime
#   ./run_test.sh -e qa -u 10 -H 10.0.0.99 -O 8080 -S http
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_DIR/config"
RESULTS_DIR="$PROJECT_DIR/results"
PLANS_DIR="$PROJECT_DIR/test-plans"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV_NAME="qa"
PLAN="AEP_ECommerce_Performance_TestPlan.jmx"
USERS="5"
RAMP_OVERRIDE=""
DURATION_OVERRIDE=""
ITERATIONS="1"
PARALLEL=false
HOST_OVERRIDE=""
PORT_OVERRIDE=""
PROTOCOL_OVERRIDE=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
log_banner(){ echo -e "${BOLD}$*${RESET}"; }

usage() {
  sed -n '/^# USAGE/,/^# ===*/p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

validate_users() {
  case "$1" in
    5|10|15) return 0 ;;
    ''|*[!0-9]*) log_error "USERS must be a positive integer (recommended: 5, 10, 15)"; exit 1 ;;
    *) log_warn "Non-standard user count: $1 (recommended: 5, 10, or 15)"; return 0 ;;
  esac
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while getopts "e:p:u:r:d:i:PH:O:S:h" opt; do
  case $opt in
    e) ENV_NAME="$OPTARG" ;;
    p) PLAN="$OPTARG" ;;
    u) USERS="$OPTARG" ;;
    r) RAMP_OVERRIDE="$OPTARG" ;;
    d) DURATION_OVERRIDE="$OPTARG" ;;
    i) ITERATIONS="$OPTARG" ;;
    P) PARALLEL=true ;;
    H) HOST_OVERRIDE="$OPTARG" ;;
    O) PORT_OVERRIDE="$OPTARG" ;;
    S) PROTOCOL_OVERRIDE="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

validate_users "$USERS"

# ---------------------------------------------------------------------------
# Load environment file
# ---------------------------------------------------------------------------
ENV_FILE="$CONFIG_DIR/env.${ENV_NAME}.sh"
if [[ ! -f "$ENV_FILE" ]]; then
  log_error "Environment file not found: $ENV_FILE"
  log_error "Available environments: $(ls "$CONFIG_DIR"/env.*.sh 2>/dev/null | xargs -n1 basename | sed 's/env\.//;s/\.sh//' | tr '\n' ' ')"
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

# Apply CLI overrides (take precedence over env file)
PROTOCOL="${PROTOCOL_OVERRIDE:-${PERF_PROTOCOL}}"
HOST="${HOST_OVERRIDE:-${PERF_HOST}}"
PORT="${PORT_OVERRIDE:-${PERF_PORT}}"
RAMP="${RAMP_OVERRIDE:-${PERF_RAMP_UP}}"
DURATION="${DURATION_OVERRIDE:-${PERF_DURATION}}"
SLA="${PERF_SLA_RESPONSE_TIME}"
# SESSION_COOKIE: env file value → shell env var fallback → empty (UI-only runs still work)
SESSION_COOKIE="${PERF_SESSION_COOKIE:-${SESSION_COOKIE:-}}"

PLAN_PATH="$PLANS_DIR/$PLAN"
if [[ ! -f "$PLAN_PATH" ]]; then
  log_error "Test plan not found: $PLAN_PATH"
  exit 1
fi

# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------
if ! command -v jmeter &>/dev/null; then
  log_error "jmeter not found on PATH. Install with: brew install jmeter"
  exit 1
fi

mkdir -p "$RESULTS_DIR"

BATCH_ID="$(date +"%Y%m%d_%H%M%S")_${ENV_NAME}_${USERS}u"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
log_banner "════════════════════════════════════════════════════════════"
log_banner "  AEP Performance Test Runner"
log_banner "════════════════════════════════════════════════════════════"
log_info "  Environment  : $(echo "$ENV_NAME" | tr '[:lower:]' '[:upper:]')"
log_info "  Target       : ${PROTOCOL}://${HOST}:${PORT}"
log_info "  Plan         : $PLAN"
log_info "  Virtual Users: $USERS"
log_info "  Ramp-up      : ${RAMP}s"
log_info "  Duration     : ${DURATION}s"
log_info "  Iterations   : $ITERATIONS  $([ "$PARALLEL" = true ] && echo "(PARALLEL)" || echo "(sequential)")"
log_info "  SLA          : ${SLA}ms"
log_info "  Session Cookie: $([ -n "$SESSION_COOKIE" ] && echo "SET (${#SESSION_COOKIE} chars)" || echo "NOT SET — API steps will fail")"
log_info "  Batch ID     : $BATCH_ID"
log_banner "════════════════════════════════════════════════════════════"
echo ""

# ---------------------------------------------------------------------------
# Single-run function
# ---------------------------------------------------------------------------
run_single() {
  local run_num="$1"
  local run_label
  run_label="$(printf "run_%02d" "$run_num")"
  local run_dir="$RESULTS_DIR/${BATCH_ID}_${run_label}"

  mkdir -p "$run_dir"

  log_info "Starting $run_label ..."

  jmeter \
    -n \
    -t "$PLAN_PATH" \
    -l "$run_dir/results.jtl" \
    -e \
    -o "$run_dir/html-report" \
    -JPROTOCOL="$PROTOCOL" \
    -JHOST="$HOST" \
    -JPORT="$PORT" \
    -JTHREAD_COUNT="$USERS" \
    -JRAMP_UP="$RAMP" \
    -JDURATION="$DURATION" \
    -JSLA_RESPONSE_TIME="$SLA" \
    -JTHINK_TIME_MEAN="${PERF_THINK_TIME_MEAN}" \
    -JTHINK_TIME_DEV="${PERF_THINK_TIME_DEV}" \
    -JSESSION_COOKIE="${SESSION_COOKIE}" \
    -j "$run_dir/jmeter.log" \
    > "$run_dir/stdout.log" 2>&1

  log_ok "$run_label complete → $run_dir/html-report/index.html"

  # Inline summary immediately after each run
  python3 "$SCRIPT_DIR/analyze_results.py" \
    "$run_dir/results.jtl" \
    --sla "$SLA" \
    --env "$ENV_NAME" \
    --run "$run_label" \
    --users "$USERS" \
    --html "$run_dir/summary.html" \
    || true
}

# ---------------------------------------------------------------------------
# Execute iterations
# ---------------------------------------------------------------------------
PIDS=()

for i in $(seq 1 "$ITERATIONS"); do
  if [[ "$PARALLEL" == true ]]; then
    run_single "$i" &
    PIDS+=($!)
  else
    run_single "$i"
  fi
done

# Wait for parallel jobs and collect exit codes
if [[ "$PARALLEL" == true ]]; then
  FAILED=0
  for pid in "${PIDS[@]}"; do
    wait "$pid" || FAILED=$((FAILED + 1))
  done
  if (( FAILED > 0 )); then
    log_error "$FAILED parallel run(s) failed."
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Aggregate report (only when multiple iterations ran)
# ---------------------------------------------------------------------------
if (( ITERATIONS > 1 )); then
  echo ""
  log_banner "════════════════════════════════════════════════════════════"
  log_banner "  Aggregate Summary — $ITERATIONS runs"
  log_banner "════════════════════════════════════════════════════════════"

  JTL_ARGS=()
  for i in $(seq 1 "$ITERATIONS"); do
    run_label="$(printf "run_%02d" "$i")"
    jtl="$RESULTS_DIR/${BATCH_ID}_${run_label}/results.jtl"
    [[ -f "$jtl" ]] && JTL_ARGS+=("$jtl")
  done

  python3 "$SCRIPT_DIR/analyze_results.py" \
    --aggregate \
    --sla "$SLA" \
    --env "$ENV_NAME" \
    --users "$USERS" \
    --html "$RESULTS_DIR/${BATCH_ID}_aggregate/summary.html" \
    "${JTL_ARGS[@]}" \
    || true

  log_ok "Aggregate report → $RESULTS_DIR/${BATCH_ID}_aggregate/summary.html"
fi

echo ""
log_ok "All runs complete. Results in: $RESULTS_DIR/"
