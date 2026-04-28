#!/usr/bin/env bash
# =============================================================================
# run_parallel.sh — Run the same test at multiple user loads simultaneously
# =============================================================================
#
# Launches separate JMeter processes for each user-count tier in parallel,
# producing independent result sets that can be compared side-by-side.
# Useful for capacity planning: see how the system behaves at 5, 10, and 15
# users at the same time.
#
# USAGE
#   ./run_parallel.sh [-e ENV] [-d DURATION] [-i ITERATIONS] [-l "5 10 15"]
#
# EXAMPLES
#   # Default: 5, 10, 15 users in parallel on QA, 5 min each
#   ./run_parallel.sh
#
#   # Custom tiers, 2 min each
#   ./run_parallel.sh -e staging -d 120 -l "5 10"
#
#   # 3 iterations per tier, all in parallel
#   ./run_parallel.sh -e qa -d 300 -i 3
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_NAME="qa"
DURATION="300"
ITERATIONS="1"
USER_TIERS="5 10 15"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

while getopts "e:d:i:l:h" opt; do
  case $opt in
    e) ENV_NAME="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    i) ITERATIONS="$OPTARG" ;;
    l) USER_TIERS="$OPTARG" ;;
    h)
      sed -n '/^# USAGE/,/^# ===*/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  AEP Parallel Load Runner${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}  Environment  : $(echo "$ENV_NAME" | tr '[:lower:]' '[:upper:]')${RESET}"
echo -e "${CYAN}  User tiers   : $USER_TIERS${RESET}"
echo -e "${CYAN}  Duration     : ${DURATION}s per tier${RESET}"
echo -e "${CYAN}  Iterations   : $ITERATIONS per tier${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════════════════${RESET}"
echo ""

PIDS=()
TIER_LABELS=()

for users in $USER_TIERS; do
  echo -e "${CYAN}[PARALLEL]${RESET} Launching ${users}-user tier ..."
  bash "$SCRIPT_DIR/run_test.sh" \
    -e "$ENV_NAME" \
    -u "$users" \
    -d "$DURATION" \
    -i "$ITERATIONS" \
    &
  PIDS+=($!)
  TIER_LABELS+=("${users}u")
done

echo ""
echo "All tiers launched. Waiting for completion ..."
echo ""

FAILED=0
for i in "${!PIDS[@]}"; do
  pid="${PIDS[$i]}"
  label="${TIER_LABELS[$i]}"
  if wait "$pid"; then
    echo -e "${GREEN}[OK]${RESET}    Tier ${label} completed."
  else
    echo -e "${RED}[FAIL]${RESET}  Tier ${label} exited with error."
    FAILED=$((FAILED + 1))
  fi
done

echo ""
if (( FAILED > 0 )); then
  echo -e "${RED}${BOLD}$FAILED tier(s) failed. Check logs in results/.${RESET}"
  exit 1
else
  echo -e "${GREEN}${BOLD}All parallel tiers completed successfully.${RESET}"
fi
