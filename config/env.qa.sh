#!/usr/bin/env bash
# =============================================================================
# Environment: QA
# Target:      https://qa-aep.aziro.net/
# =============================================================================
# Source this file before running tests, or let run_test.sh load it via -e qa
#   source config/env.qa.sh
# =============================================================================

export PERF_ENV="qa"
export PERF_PROTOCOL="https"
export PERF_HOST="qa-aep.aziro.net"
export PERF_PORT="443"

# SLA thresholds (milliseconds)
export PERF_SLA_RESPONSE_TIME="3000"
export PERF_CONNECT_TIMEOUT="10000"
export PERF_RESPONSE_TIMEOUT="30000"

# Think-time (milliseconds)
export PERF_THINK_TIME_MEAN="1000"
export PERF_THINK_TIME_DEV="500"

# Default load profile (overridden at runtime by -t / -r / -d flags)
export PERF_THREAD_COUNT="5"
export PERF_RAMP_UP="10"
export PERF_DURATION="300"
