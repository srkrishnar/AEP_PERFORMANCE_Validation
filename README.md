# AEP ECommerce — Performance Test Suite

End-to-end performance test framework for the AEP ECommerce platform.
Built on Apache JMeter 5.6+, with environment-aware configuration, parameterised
load profiles, parallel execution, and automated HTML reporting.

---

## Table of Contents

1. [Folder Structure](#folder-structure)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Environment Configuration](#environment-configuration)
5. [Running Tests](#running-tests)
   - [Smoke Test](#smoke-test)
   - [Single Load Run](#single-load-run)
   - [Repeated Runs (iterations)](#repeated-runs-iterations)
   - [Parallel Load Tiers](#parallel-load-tiers)
6. [Load Profiles](#load-profiles)
7. [Test Plan Parameters](#test-plan-parameters)
8. [Results & Reports](#results--reports)
9. [Analyzing Results](#analyzing-results)
10. [Test Data](#test-data)
11. [CI/CD Integration](#cicd-integration)
12. [Troubleshooting](#troubleshooting)

---

## Folder Structure

```
jmeter/
├── test-plans/
│   └── AEP_ECommerce_Performance_TestPlan.jmx   # Generic test plan
│
├── scripts/
│   ├── run_test.sh          # Main test runner (env-aware, parameterised)
│   ├── run_smoke.sh         # Quick 1-user / 30-second sanity check
│   ├── run_parallel.sh      # Parallel multi-tier load launcher
│   └── analyze_results.py   # Terminal + HTML results analyzer
│
├── config/
│   ├── env.qa.sh            # QA environment variables
│   ├── env.staging.sh       # Staging environment variables
│   ├── env.prod.sh          # Production environment variables (use with care)
│   └── test_data.csv        # Parameterised user and product data
│
├── results/                 # Generated output — git-ignored
│   └── <batch_id>/
│       ├── results.jtl      # Raw JMeter CSV data
│       ├── jmeter.log       # JMeter execution log
│       ├── stdout.log       # Process stdout
│       ├── summary.html     # Custom HTML report (this framework)
│       └── html-report/     # JMeter built-in HTML dashboard
│           └── index.html
│
├── lib/                     # Custom JMeter plugin JARs
└── README.md
```

---

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Apache JMeter | 5.6+ | `brew install jmeter` |
| Python | 3.9+ | `brew install python` |
| Bash | 4.0+ | Pre-installed on macOS/Linux |

Verify everything is on your `PATH`:

```bash
jmeter --version
python3 --version
```

---

## Quick Start

```bash
# 1. Navigate to the scripts directory
cd "jmeter/scripts"

# 2. Make scripts executable (first time only)
chmod +x run_test.sh run_smoke.sh run_parallel.sh

# 3. Verify connectivity with a smoke test (1 user, 30 s)
./run_smoke.sh

# 4. Run a standard load test on QA with 10 virtual users
./run_test.sh -e qa -u 10

# 5. Open the HTML report
open ../results/<batch_id>/summary.html
```

---

## Environment Configuration

Environment files live in `config/` and define target URL, ports, SLA thresholds,
and default load parameters. They are sourced automatically by the run scripts.

| File | Environment | Base URL |
|------|------------|----------|
| `env.qa.sh` | QA | `https://qa-aep.aziro.net/` |
| `env.staging.sh` | Staging | `https://staging-aep.aziro.net/` |
| `env.prod.sh` | Production | `https://aep.aziro.net/` |

### Environment variables set by each file

| Variable | Description |
|----------|-------------|
| `PERF_PROTOCOL` | `http` or `https` |
| `PERF_HOST` | Target hostname |
| `PERF_PORT` | Target port |
| `PERF_SLA_RESPONSE_TIME` | P90 SLA threshold (ms) |
| `PERF_CONNECT_TIMEOUT` | Connection timeout (ms) |
| `PERF_RESPONSE_TIMEOUT` | Response timeout (ms) |
| `PERF_THINK_TIME_MEAN` | Mean think time between requests (ms) |
| `PERF_THINK_TIME_DEV` | Think time deviation (ms) |
| `PERF_THREAD_COUNT` | Default virtual user count |
| `PERF_RAMP_UP` | Default ramp-up seconds |
| `PERF_DURATION` | Default test duration seconds |

You can also source an env file directly in your shell:

```bash
source config/env.qa.sh
echo $PERF_HOST   # → qa-aep.aziro.net
```

---

## Running Tests

All scripts live in `jmeter/scripts/`. Run them from that directory.

### Smoke Test

Runs 1 virtual user for 30 seconds to verify the target is reachable and all
endpoints respond correctly. Run this before any load test.

```bash
./run_smoke.sh                     # QA (default)
./run_smoke.sh -e staging          # Staging
./run_smoke.sh -e qa -H 10.0.0.50  # Override host
```

---

### Single Load Run

```bash
# Syntax
./run_test.sh -e ENV -u USERS [OPTIONS]

# Examples
./run_test.sh -e qa -u 5             # 5 users, QA, env-default duration
./run_test.sh -e qa -u 10            # 10 users
./run_test.sh -e qa -u 15            # 15 users
./run_test.sh -e qa -u 10 -d 600     # 10 users, 10-minute soak
./run_test.sh -e staging -u 10       # 10 users against staging
```

#### All flags

| Flag | Description | Default |
|------|-------------|---------|
| `-e ENV` | Environment: `qa`, `staging`, `prod` | `qa` |
| `-p PLAN` | Test plan filename (inside `test-plans/`) | `AEP_ECommerce_Performance_TestPlan.jmx` |
| `-u USERS` | Virtual user count: `5`, `10`, `15` or any int | `5` |
| `-r RAMP` | Ramp-up seconds | env preset |
| `-d DURATION` | Test duration seconds | env preset |
| `-i ITERATIONS` | Number of sequential test runs | `1` |
| `-P` | Run iterations in parallel instead of sequentially | off |
| `-H HOST` | Override hostname | env preset |
| `-O PORT` | Override port | env preset |
| `-S PROTOCOL` | Override protocol `http`/`https` | env preset |
| `-h` | Print help and exit | — |

---

### Repeated Runs (iterations)

Use `-i` to run the same test plan multiple times and get trend data and
averaged metrics. Runs are sequential by default; add `-P` for parallel.

```bash
# 3 sequential runs — useful for baseline consistency checks
./run_test.sh -e qa -u 10 -d 300 -i 3

# 3 parallel runs — maximises concurrency for stress testing
./run_test.sh -e qa -u 10 -d 300 -i 3 -P

# 5 runs, 1 user each — soak over 25 minutes
./run_test.sh -e qa -u 1 -d 300 -i 5
```

Each iteration produces its own result folder (`run_01`, `run_02`, etc.).
After all iterations complete, an aggregate report is automatically generated.

---

### Parallel Load Tiers

Run the system at 5, 10, and 15 virtual users simultaneously to build a
capacity curve in a single session.

```bash
# Default: 5 / 10 / 15 users, 5 min each, on QA
./run_parallel.sh

# Custom tiers, 2 min each
./run_parallel.sh -e staging -d 120 -l "5 10"

# 2 iterations per tier in parallel
./run_parallel.sh -e qa -d 300 -i 2

# All flags
#   -e ENV       Environment
#   -d DURATION  Seconds per tier
#   -i ITER      Iterations per tier
#   -l "N M ..."  Space-separated user tiers (quoted)
```

---

## Load Profiles

| Profile | Users | Ramp | Duration | Use case |
|---------|-------|------|----------|----------|
| Smoke | 1 | 1s | 30s | Connectivity check |
| Light | 5 | 10s | 300s | Pre-release sanity |
| Standard | 10 | 15s | 300s | Sprint regression |
| Heavy | 15 | 20s | 300s | Release validation |
| Soak | 10 | 15s | 3600s | Overnight stability |
| Stress | 15 | 10s | 600s | Breaking-point search |

---

## Test Plan Parameters

All parameters in the JMX can be overridden at runtime via `-J` JMeter flags
(handled automatically by `run_test.sh`).

| Parameter | QA Default | Description |
|-----------|-----------|-------------|
| `PROTOCOL` | `https` | `http` or `https` |
| `HOST` | `qa-aep.aziro.net` | Target hostname |
| `PORT` | `443` | Target port |
| `THREAD_COUNT` | `5` | Virtual users |
| `RAMP_UP` | `10` | Ramp-up period (seconds) |
| `DURATION` | `300` | Test duration (seconds) |
| `THINK_TIME_MEAN` | `1000` | Mean think time (ms) |
| `THINK_TIME_DEV` | `500` | Think time deviation (ms) |
| `CONNECT_TIMEOUT` | `10000` | Connection timeout (ms) |
| `RESPONSE_TIMEOUT` | `30000` | Response timeout (ms) |
| `SLA_RESPONSE_TIME` | `3000` | P90 pass/fail threshold (ms) |
| `PRODUCT_ID_1` | `B00CP92UHU` | Test product ID 1 |
| `PRODUCT_ID_2` | `B0775268NR` | Test product ID 2 |

---

## Results & Reports

Each test run produces a batch folder under `results/`:

```
results/
└── 20260427_193600_qa_10u_run_01/
    ├── results.jtl          ← raw JMeter CSV (all samples)
    ├── jmeter.log           ← JMeter engine log
    ├── stdout.log           ← process stdout
    ├── summary.html         ← AEP custom dark-themed HTML report
    └── html-report/
        └── index.html       ← JMeter built-in dashboard
```

Open the custom report (recommended):

```bash
open results/<batch_id>/summary.html
```

The **AEP custom report** includes:
- Executive KPI banner (verdict, avg, P90, error rate, throughput)
- Colour-coded transaction table (P90 and error rate highlighted red on violation)
- Run comparison trend chart (multi-iteration runs)
- Full dark-themed responsive layout

---

## Analyzing Results

```bash
# Analyze a single run
python3 scripts/analyze_results.py results/<run>/results.jtl

# With custom thresholds
python3 scripts/analyze_results.py results/<run>/results.jtl \
  --sla 2000 --error-rate 0.5

# Compare multiple runs (aggregate)
python3 scripts/analyze_results.py --aggregate \
  results/run_01/results.jtl \
  results/run_02/results.jtl \
  results/run_03/results.jtl \
  --sla 3000 --env qa --users 10 \
  --html results/aggregate/summary.html

# All options
#   --sla MS          P90 SLA in milliseconds (default: 3000)
#   --error-rate PCT  Max error rate % (default: 1.0)
#   --env NAME        Label shown in report
#   --run LABEL       Run label shown in report
#   --users N         User count shown in report
#   --html PATH       Write HTML report to this path
#   --aggregate       Treat each JTL as a separate run
```

Exit codes: `0` = all pass, `1` = violation detected, `2` = input error.

---

## Test Data

`config/test_data.csv` provides parameterised user and product data.
JMeter reads this file round-robin — each virtual user picks the next row.

Columns: `username`, `password`, `product_id`, `quantity`, `category`,
`search_keyword`, `coupon_code`

To wire it into the test plan, add a **CSV Data Set Config** element:

| Field | Value |
|-------|-------|
| Filename | `${__P(DATA_DIR,../../config)}/test_data.csv` |
| Variable Names | `username,password,product_id,...` |
| Sharing mode | `All threads` |
| Recycle on EOF | `True` |

Add more rows to scale the dataset beyond the default 10 entries.

---

## CI/CD Integration

`run_test.sh` exits non-zero on JMeter failure. `analyze_results.py` exits
non-zero on SLA violation. Chain them in your pipeline for an automated gate.

### GitHub Actions

```yaml
name: Performance Tests

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        default: 'qa'
      users:
        description: 'Virtual users'
        default: '10'
      duration:
        description: 'Duration (seconds)'
        default: '300'

jobs:
  perf-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install JMeter
        run: |
          wget -q https://downloads.apache.org/jmeter/binaries/apache-jmeter-5.6.3.tgz
          tar -xzf apache-jmeter-5.6.3.tgz
          echo "$PWD/apache-jmeter-5.6.3/bin" >> $GITHUB_PATH

      - name: Run performance test
        run: |
          cd jmeter/scripts
          chmod +x run_test.sh
          ./run_test.sh \
            -e "${{ github.event.inputs.environment }}" \
            -u "${{ github.event.inputs.users }}" \
            -d "${{ github.event.inputs.duration }}" \
            -i 3

      - name: Analyze & gate
        run: |
          LATEST=$(ls -td jmeter/results/*run_01 | head -1)
          python3 jmeter/scripts/analyze_results.py \
            "$LATEST/results.jtl" \
            --sla 3000 --error-rate 1.0

      - name: Upload reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: perf-reports-${{ github.run_id }}
          path: jmeter/results/
```

### Azure DevOps

```yaml
- script: |
    cd jmeter/scripts
    ./run_test.sh -e qa -u 10 -d 300 -i 3
    LATEST=$(ls -td ../results/*run_01 | head -1)
    python3 analyze_results.py "$LATEST/results.jtl" --sla 3000
  displayName: 'Run JMeter Performance Tests'

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: 'jmeter/results'
    artifactName: 'perf-reports'
  condition: always()
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `jmeter: command not found` | JMeter not on PATH | `brew install jmeter` or set `JMETER_HOME` |
| `Test plan not found` | Wrong `-p` value | Check `test-plans/` for exact filename |
| `Environment file not found` | Wrong `-e` value | Use `qa`, `staging`, or `prod` |
| All requests fail immediately | Wrong host/port | Run smoke test; verify env file |
| P90 > SLA but low error rate | Slow server, not broken | Tune `SLA_RESPONSE_TIME` or investigate server |
| HTML report dir already exists | Previous run left data | Delete `results/<run>/html-report/` before re-run |
| High error rate on one endpoint | Bug or rate-limiting | Check `html-report` for assertion failure detail |

### Useful JMeter flags for debugging

```bash
# Increase JVM heap for large tests
export HEAP="-Xms1g -Xmx4g"

# Enable debug logging
jmeter -n -t test-plans/... -Lorg.apache.jmeter=DEBUG ...

# Disable SSL certificate validation (for self-signed certs)
# Add to test plan: HTTP Request Defaults → Advanced → SSL
```

---

## Git Ignore

`results/` is git-ignored — never commit raw JTL output or HTML reports.
Commit: test plans, scripts, env config files, `test_data.csv`, and this README.
