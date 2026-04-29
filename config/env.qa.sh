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

# Session cookie for authenticated API calls (TC_00 through TC_19)
# HOW TO GET:
#   1. Open Chrome → https://qa-aep.aziro.net → log in
#   2. DevTools (F12) → Network tab → click any API request (e.g. /profile)
#   3. Request Headers → Cookie → copy the entire value
#   4. Paste below (one line, no quotes)
export PERF_SESSION_COOKIE="i18next=en-US; x-user-id=6; x-consent=granted; session_token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJrVTlpZXlVem1aTVhkVTdJTGFzVl9SMnFYWWlCZjRCS2lJWlZ5YWREV3FrIiwiYWVwX3VzZXJfaWQiOjYsInNjb3BlIjoiYWVwOnVzZXI6cmVhZCBhZXA6cHJvZmlsZTp3cml0ZSIsImlzcyI6InFhLWFlcC5hemlyby5uZXQiLCJhdWQiOlsiYWVwLXVzZXItc2VydmljZSJdLCJpYXQiOjE3Nzc0NTYzODIsImV4cCI6MTc3NzQ1ODE4Mn0.RNIjGZObA_kVevV7sgSfhqrj742gFGGXFR9cNSmTRes; X-Session-ID=04eefa01-a014-326a-b004-4157694f4a8b"
