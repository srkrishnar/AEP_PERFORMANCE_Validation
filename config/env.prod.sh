#!/usr/bin/env bash
# =============================================================================
# Environment: Production
# WARNING: Use with caution — low thread count, short duration only.
# =============================================================================

export PERF_ENV="prod"
export PERF_PROTOCOL="https"
export PERF_HOST="aep.aziro.net"
export PERF_PORT="443"

export PERF_SLA_RESPONSE_TIME="2000"
export PERF_CONNECT_TIMEOUT="10000"
export PERF_RESPONSE_TIMEOUT="30000"

export PERF_THINK_TIME_MEAN="2000"
export PERF_THINK_TIME_DEV="1000"

export PERF_THREAD_COUNT="5"
export PERF_RAMP_UP="30"
export PERF_DURATION="120"
