#!/usr/bin/env bash
# =============================================================================
# Environment: Staging
# =============================================================================

export PERF_ENV="staging"
export PERF_PROTOCOL="https"
export PERF_HOST="staging-aep.aziro.net"
export PERF_PORT="443"

export PERF_SLA_RESPONSE_TIME="3000"
export PERF_CONNECT_TIMEOUT="10000"
export PERF_RESPONSE_TIMEOUT="30000"

export PERF_THINK_TIME_MEAN="1000"
export PERF_THINK_TIME_DEV="500"

export PERF_THREAD_COUNT="10"
export PERF_RAMP_UP="15"
export PERF_DURATION="300"
