# AEP ECommerce — Performance Test Suite

End-to-end performance test framework for the AEP ECommerce platform.
Built on Apache JMeter 5.6+, covering the complete user journey from browsing
through checkout and order confirmation, with environment-aware configuration,
parameterised load profiles, and automated HTML reporting.

---

## Table of Contents

1. [Folder Structure](#folder-structure)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Test Journey — End-to-End Flow](#test-journey--end-to-end-flow)
5. [How to Run](#how-to-run)
   - [Smoke Test](#smoke-test)
   - [Single Load Run](#single-load-run)
   - [Repeated Runs](#repeated-runs)
   - [Parallel Load Tiers](#parallel-load-tiers)
6. [Load Profiles](#load-profiles)
7. [Test Plan Parameters](#test-plan-parameters)
8. [Security Standards](#security-standards)
9. [Results and Reports](#results-and-reports)
10. [Analyzing Results](#analyzing-results)
11. [Test Data](#test-data)
12. [CI/CD Integration](#cicd-integration)
13. [Troubleshooting](#troubleshooting)

---

## Folder Structure

```
jmeter/
├── test-plans/
│   └── AEP_ECommerce_Performance_TestPlan.jmx   # Main test plan (19 TCs)
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
│       ├── summary.html     # AEP custom HTML report
│       └── html-report/
│           └── index.html   # JMeter built-in HTML dashboard
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

# 3. Refresh your session cookie in config/env.qa.sh (expires ~30 min)
#    Open Chrome → https://qa-aep.aziro.net → log in
#    DevTools (F12) → Network → any API request → Request Headers → Cookie
#    Paste the full value into PERF_SESSION_COOKIE in config/env.qa.sh

# 4. Run: 5 users, each loops 3 times → 15 hits per TC
./run_test.sh -e qa -u 5 -i 3

# 5. Open the custom HTML report
open ../results/<batch_id>_run_01/summary.html
```

---

## Test Journey — End-to-End Flow

The test plan simulates a complete customer journey in strict order.
Every step has a **200 OK assertion** and a **3-second SLA assertion**.
API steps additionally carry a **JSON path assertion** where the field is
deterministic.

```
PHASE 1 — Browse / Merchandising (UI layer)
────────────────────────────────────────────
TC_01  GET  /merchandise                                     Merchandise landing page
TC_02  GET  /merchandise/shop                                Shop default listing
TC_03  GET  /merchandise/shop?sort=price_asc                 Sort by price ascending
TC_04  GET  /merchandise/shop?sort=price_desc                Sort by price descending
TC_05  GET  /merchandise/shop?sort=rating_desc               Sort by rating
TC_06  GET  /merchandise/shop?q=mobile                       Keyword search
TC_07  GET  /merchandise/mobile-and-accessories-…            Category: Smartphones
TC_08  GET  /merchandise/mobile-and-accessories-…-apple      Sub-category: Apple
TC_09  GET  /merchandise/apparel                             Category: Apparel

PHASE 2 — API: Category & Product Discovery
────────────────────────────────────────────
TC_10  GET  /integrate/api/v1/categories/categoryTree        Full category tree
TC_11  GET  /integrate/api/v1/products/sku/{SKU}             Product detail by SKU
TC_12  GET  /integrate/api/v1/products/similarProducts       Similar products

PHASE 3 — API: Cart & Checkout
────────────────────────────────────────────
TC_13  POST /integrate/api/v1/carts/items                    Add product to cart
TC_15  GET  /integrate/api/v1/checkout/process               Checkout with delivery address
             ?includeDeliveryAddress=true
TC_16  GET  /integrate/api/v1/delivery/addresses             Saved delivery addresses
TC_17  POST /integrate/api/v1/orders/place                   Place the order

PHASE 4 — API: Post-Order
────────────────────────────────────────────
TC_18  GET  /integrate/api/v1/profile                        User profile
TC_19  GET  /integrate/api/v1/orders/confirmation/{ORDER_ID} Order confirmation
```

### Assertions per step

| Assertion type | Applied to | Validates |
|----------------|-----------|-----------|
| Response Code  | All 19 TCs | HTTP 200 (or 200/201 for POSTs) |
| Duration SLA   | All 19 TCs | Response time ≤ `SLA_RESPONSE_TIME` (default 3000 ms) |
| JSON Path      | TC_10, TC_11, TC_19 | Response body contains expected field |

---

## How to Run

All commands are run from the `jmeter/scripts/` directory.

```bash
cd "jmeter/scripts"
```

---

### Key Flags

| Flag | What it does | Default |
|------|-------------|---------|
| `-u` | Number of virtual users | `5` |
| `-i` | How many times each user runs the full journey (loops) | `1` |
| `-R` | Number of separate JMeter runs (one after another, or in parallel) | `1` |
| `-P` | Run the `-R` separate runs in parallel instead of one by one | off |
| `-e` | Environment: `qa`, `staging`, `prod` | `qa` |

> **Hits per TC = `-u` × `-i`**
> Example: `-u 5 -i 3` → 5 users × 3 loops = **15 hits per test case**

---

### Sequential (one after another)

Each user runs the full journey from start to finish, one loop at a time.
All users run together inside a single JMeter process.

```bash
# 5 users, each loops 3 times → 15 hits per TC — ONE report
./run_test.sh -e qa -u 5 -i 3

# 10 users, each loops once → 10 hits per TC
./run_test.sh -e qa -u 10

# 5 users × 3 loops, repeated as 2 separate runs (run_01, run_02)
# Each report will show 15 hits. An aggregate report is also generated.
./run_test.sh -e qa -u 5 -i 3 -R 2
```

**Reports saved to:**
```
results/<batch_id>_run_01/summary.html
results/<batch_id>_run_02/summary.html   ← only if -R 2 or more
results/<batch_id>_aggregate/summary.html ← only if -R 2 or more
```

---

### Parallel (all runs at the same time)

Use `-P` together with `-R` to launch multiple JMeter runs simultaneously.
Useful for stress testing or comparing how the server handles concurrent load.

```bash
# 3 separate runs all firing at the same time
# Each run: 5 users × 3 loops = 15 hits per TC
./run_test.sh -e qa -u 5 -i 3 -R 3 -P
```

**Reports saved to:**
```
results/<batch_id>_run_01/summary.html
results/<batch_id>_run_02/summary.html
results/<batch_id>_run_03/summary.html
results/<batch_id>_aggregate/summary.html
```

---

### Quick Reference

| What you want | Command |
|---------------|---------|
| 5 users, 1 loop → 5 hits | `./run_test.sh -e qa -u 5` |
| 5 users, 3 loops → **15 hits** | `./run_test.sh -e qa -u 5 -i 3` |
| 10 users, 3 loops → **30 hits** | `./run_test.sh -e qa -u 10 -i 3` |
| 3 separate runs, one by one | `./run_test.sh -e qa -u 5 -i 3 -R 3` |
| 3 separate runs, all at once | `./run_test.sh -e qa -u 5 -i 3 -R 3 -P` |

---

## Load Profiles

| Profile | Users | Ramp | Duration | Use case |
|---------|-------|------|----------|----------|
| Smoke | 1 | 1 s | 30 s | Connectivity sanity check |
| Light | 5 | 10 s | 300 s | Pre-release sanity |
| Standard | 10 | 15 s | 300 s | Sprint regression |
| Heavy | 15 | 20 s | 300 s | Release validation |
| Soak | 10 | 15 s | 3600 s | Overnight stability |
| Stress | 15 | 10 s | 600 s | Breaking-point search |

---

## Test Plan Parameters

All parameters can be overridden at runtime via `-J` JMeter flags.

| Parameter | Default (QA) | Description |
|-----------|-------------|-------------|
| `PROTOCOL` | `https` | `http` or `https` |
| `HOST` | `qa-aep.aziro.net` | Target hostname |
| `PORT` | `443` | Target port |
| `THREAD_COUNT` | `5` | Virtual users (set by `-u`) |
| `LOOP_COUNT` | `1` | Journey loops per user (set by `-i`) |
| `RAMP_UP` | `10` | Ramp-up period (seconds) |
| `DURATION` | `600` | Max test duration guard (seconds) |
| `THINK_TIME_MEAN` | `500` | Mean think time between steps (ms) |
| `THINK_TIME_DEV` | `200` | Think time standard deviation (ms) |
| `CONNECT_TIMEOUT` | `10000` | Connection timeout (ms) |
| `RESPONSE_TIMEOUT` | `30000` | Response timeout (ms) |
| `SLA_RESPONSE_TIME` | `3000` | P90 pass/fail threshold (ms) |
| `SESSION_COOKIE` | — | Full browser cookie string for auth (see below) |

---

## Security Standards

These standards apply to all performance test runs. Failure to follow them
risks exposing production data, triggering rate-limits, or violating compliance.

### Authentication & Credentials

- **Never hard-code** tokens, passwords, or API keys in the `.jmx` file or
  scripts. Use environment variables or a secrets manager.
- Store test credentials in `config/test_data.csv` and ensure the file is
  listed in `.gitignore`.
- Rotate test credentials after each major test campaign.

### TLS / HTTPS

- All tests against QA, Staging, and Production **must** use `PROTOCOL=https`.
- Do not disable SSL certificate validation in JMeter unless testing against
  a locally hosted self-signed cert. Never disable it for QA or above.
- If a self-signed cert is needed on local only:
  ```bash
  # In JMeter GUI: Options → SSL Manager → import cert
  # Or set in jmeter.properties:
  # httpclient.parameters.file=httpclient.parameters
  # Add: https.use.cached.ssl.context=false
  ```

### Test Scope & Rate Limiting

- **Never run** stress or heavy load profiles against Production without
  written approval from the engineering lead.
- Use `THREAD_COUNT ≤ 15` for QA. Production load must be pre-approved and
  run during off-peak hours only.
- Honour any rate-limit headers (`Retry-After`, `X-RateLimit-*`) returned
  by the API — add wait logic if the API returns 429.

### Data Handling

- POST bodies (`Add to Cart`, `Place Order`) use synthetic test data only.
  Never use real customer names, addresses, or payment details.
- All test-generated orders should be tagged or placed in a known test account
  so they can be identified and cleaned up after a run.
- `results/` is git-ignored — never commit `.jtl` files or HTML reports
  as they may contain response bodies with PII.

### Headers & Identity

- The `User-Agent` header is set to `JMeterPerfTest/3.0` so test traffic is
  identifiable in server logs and WAF dashboards.
- The `X-Requested-With: JMeterPerformanceTest` header is included globally
  so ops can filter performance traffic from real user traffic in dashboards.
- If the target has a WAF or bot-protection layer, whitelist the test machine
  IP and the custom User-Agent before running.

### Secrets Scanning

Before committing any changes run:

```bash
# Scan for accidental credential exposure
grep -rE "(password|token|secret|apikey|api_key)\s*=" \
  jmeter/test-plans/ jmeter/config/ jmeter/scripts/
```

---

## Results and Reports

Each test run produces a batch folder under `results/`:

```
results/
└── 20260429_120000_qa_10u_run_01/
    ├── results.jtl          ← raw JMeter CSV (all samples)
    ├── jmeter.log           ← JMeter engine log
    ├── stdout.log           ← process stdout
    ├── summary.html         ← AEP custom HTML report
    └── html-report/
        └── index.html       ← JMeter built-in dashboard
```

Open the custom report (recommended):

```bash
open results/<batch_id>/summary.html
```

The AEP custom report includes:

- Executive KPI banner: verdict, avg response, P90, error rate, throughput
- Colour-coded transaction table (P90 and error rate highlighted red on SLA breach)
- Journey phase grouping (Browse / Discovery / Cart / Post-Order)
- Run comparison trend chart for multi-iteration runs

---

## Analyzing Results

```bash
# Single run
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
```

| Flag | Description |
|------|-------------|
| `--sla MS` | P90 SLA in milliseconds (default 3000) |
| `--error-rate PCT` | Max acceptable error rate % (default 1.0) |
| `--env NAME` | Label shown in report |
| `--run LABEL` | Run label shown in report |
| `--users N` | User count shown in report |
| `--html PATH` | Write HTML report to this path |
| `--aggregate` | Treat each JTL as a separate run for comparison |

Exit codes: `0` = all pass, `1` = SLA or error-rate violation, `2` = input error.

---

## Test Data

`config/test_data.csv` provides parameterised user and product data.
JMeter reads this file round-robin — each virtual user picks the next row.

Columns: `username`, `password`, `product_sku`, `quantity`, `category`,
`search_keyword`, `order_id`

To wire it into the test plan, add a **CSV Data Set Config** element in JMeter GUI:

| Field | Value |
|-------|-------|
| Filename | `${__P(DATA_DIR,../../config)}/test_data.csv` |
| Variable Names | `username,password,product_sku,quantity,category,search_keyword,order_id` |
| Sharing mode | `All threads` |
| Recycle on EOF | `True` |

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
            -d "${{ github.event.inputs.duration }}"

      - name: Analyze and gate
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
    ./run_test.sh -e qa -u 10 -d 300
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

## Session Cookie (Authentication)

API steps TC_13 through TC_19 require an authenticated session.
The `SESSION_COOKIE` expires roughly every 30 minutes, so refresh it before each test run.

**How to get a fresh cookie:**

1. Open Chrome → `https://qa-aep.aziro.net` → log in with the test account
2. Open DevTools (`F12`) → **Network** tab → click any API request (e.g. `/profile`)
3. Go to **Request Headers** → find `Cookie:` → copy the entire value
4. Paste it into `config/env.qa.sh` as `PERF_SESSION_COOKIE="<paste here>"`

**Signs the cookie has expired:**
- TC_13 (Add to Cart) returns 401
- TC_17 (Submit Order) shows 0 ms / 0 requests

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `jmeter: command not found` | JMeter not on PATH | `brew install jmeter` or export `JMETER_HOME` |
| `Test plan not found` | Wrong `-p` value | Check `test-plans/` for exact filename |
| `Environment file not found` | Wrong `-e` value | Use `qa`, `staging`, or `prod` |
| All requests fail immediately | Wrong host/port | Run smoke test; verify env file |
| TC_13 / TC_17 return 401 | Missing auth token | Ensure session/cookie is set before cart steps |
| TC_11 JSON assertion fails | SKU not found | Verify `PRODUCT_SKU` exists in the QA catalogue |
| P90 > SLA but low error rate | Slow server | Tune `SLA_RESPONSE_TIME` or investigate server-side |
| HTML report dir already exists | Previous run left data | Delete `results/<run>/html-report/` and re-run |
| High error rate on one endpoint | Bug or rate-limiting | Check `html-report` for assertion failure details |
| 429 Too Many Requests | Rate-limit hit | Increase `THINK_TIME_MEAN` or reduce `THREAD_COUNT` |

### Useful JMeter flags

```bash
# Increase JVM heap for large tests
export HEAP="-Xms1g -Xmx4g"

# Debug logging
jmeter -n -t test-plans/AEP_ECommerce_Performance_TestPlan.jmx \
  -Lorg.apache.jmeter=DEBUG -l results.jtl

# Override multiple parameters inline
jmeter -n \
  -t test-plans/AEP_ECommerce_Performance_TestPlan.jmx \
  -JHOST=qa-aep.aziro.net \
  -JTHREAD_COUNT=5 \
  -JDURATION=60 \
  -JPRODUCT_SKU=B000G250SO \
  -JORDER_ID=10168 \
  -l results/quick/results.jtl \
  -e -o results/quick/html-report
```

---

## Git Ignore

`results/` is git-ignored — never commit raw JTL output, HTML reports, or
`test_data.csv` if it contains real credentials.

Commit: test plans, scripts, env config files (without secrets), and this README.
