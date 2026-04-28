# JMeter Reference Guide — AEP Performance Team

Quick reference for team members running or maintaining the AEP performance suite.

---

## JMeter CLI Cheat Sheet

```bash
# Non-GUI run (always use this in CI and scripts)
jmeter -n -t <plan.jmx> -l <results.jtl> -e -o <html-dir>

# Override a UDV (User Defined Variable) at runtime
jmeter -n -t plan.jmx -JHOST=myhost -JPORT=443 -JTHREAD_COUNT=10

# Generate HTML report from existing JTL
jmeter -g results.jtl -o html-report/

# Increase heap for large tests (set before running)
export HEAP="-Xms512m -Xmx2g"
```

---

## JMeter Test Plan Elements Used

### Thread Group (TG_01_Full_Endpoint_Validation)
Controls the number of virtual users, ramp-up time, and test duration.

| Property | Variable | Effect |
|----------|----------|--------|
| Number of Threads | `${THREAD_COUNT}` | Concurrent virtual users |
| Ramp-Up Period | `${RAMP_UP}` | Seconds to reach full user count |
| Duration | `${DURATION}` | How long the test runs |
| Loop Count | -1 (forever) | Test runs until duration elapses |

### Transaction Controllers (TC_*)
Group related HTTP samplers into logical transactions. The transaction response
time includes all child sampler times. Used for business-level reporting.

### HTTP Sampler (HTTP_GET_*)
Individual HTTP requests. Named with method prefix and sequence number for easy
identification in results.

### Response Assertions (RA_*)
Validate HTTP status codes. Failures are recorded in `results.jtl` with
`success=false`.

### Duration Assertions (DA_*)
Fail a sample if it exceeds `${SLA_RESPONSE_TIME}`. This creates assertion
failures in JTL but does NOT stop the test.

### Gaussian Random Timer (TMR_ThinkTime_*)
Simulates realistic user think time between actions.
- Mean: `${THINK_TIME_MEAN}` ms
- Deviation: `${THINK_TIME_DEV}` ms
- Actual delay = Gaussian(mean, dev) — can be 0 if deviation > mean

### HTTP Request Defaults (HTTP_Request_Defaults)
Sets host, port, protocol, and timeouts globally so individual samplers only
specify the path.

### HTTP Cookie Manager
Clears cookies at the start of each iteration, simulating a fresh browser session.

### HTTP Header Manager (HM_Global_Headers)
Sends realistic browser headers to avoid server-side bot detection.

---

## Understanding JTL Files

JTL files are CSV with these key columns:

| Column | Description |
|--------|-------------|
| `timeStamp` | Epoch milliseconds when the sample started |
| `elapsed` | Response time in milliseconds |
| `label` | Sampler or transaction name |
| `responseCode` | HTTP status code |
| `responseMessage` | Status message |
| `threadName` | Thread group and thread number |
| `success` | `true` / `false` |
| `bytes` | Response size in bytes |
| `latency` | Time to first byte (ms) |
| `connect` | TCP connection time (ms) |

---

## Key Metrics Explained

| Metric | How Calculated | Why It Matters |
|--------|---------------|----------------|
| **Avg response** | Mean of all elapsed values | General performance indicator |
| **Median (P50)** | 50th percentile | Typical user experience |
| **P90** | 90th percentile | SLA gate — 90% of users see this or better |
| **P95** | 95th percentile | Near-worst-case experience |
| **P99** | 99th percentile | True worst-case (outliers) |
| **Error rate** | (failures / total) × 100 | Reliability indicator |
| **Throughput** | samples / test duration | Capacity measure (req/s) |

### Why P90 for SLA?

P90 means 90% of users experienced a response time at or below this value.
It is the standard SLA metric for web applications because it excludes
the top 10% of outliers (which may be caused by GC pauses, network blips,
etc.) while still capturing the experience of the vast majority of users.

---

## Common SLA Thresholds

| Endpoint Type | P90 Target | Notes |
|--------------|-----------|-------|
| Static page (CDN) | < 300ms | Should be near-instant |
| API read (GET) | < 1000ms | Including DB query |
| API write (POST/PUT) | < 2000ms | Including validation + DB write |
| Search | < 1500ms | Elasticsearch or similar |
| Checkout flow | < 3000ms | Complex transaction |

---

## Tuning Tips

### Too many connection errors
- Increase `CONNECT_TIMEOUT` in env file (default 10 s)
- Verify firewall rules allow JMeter → target
- Check if target has rate-limiting or IP blocking

### Response times high but no errors
- Target server CPU/memory may be saturated — check server metrics alongside test
- DB query plan may not be cached — warm up with a smoke test first
- Consider increasing think time to reduce request rate

### JMeter uses too much memory
```bash
export HEAP="-Xms1g -Xmx4g"   # before running jmeter
```

### Disable SSL verification (self-signed certs)
Add to `user.properties` in JMeter's `bin/` directory:
```properties
https.use.cached.ssl.context=false
```
Or add a `BeanShell PreProcessor` with:
```java
import org.apache.http.conn.ssl.NoopHostnameVerifier;
```

---

## Result Folder Naming Convention

```
results/
└── <YYYYMMDD_HHMMSS>_<env>_<users>u_<run_label>/
```

Example: `20260427_193600_qa_10u_run_01`

The batch ID groups all iterations of a single execution session:
`20260427_193600_qa_10u_run_01`, `..._run_02`, `..._run_03`, `..._aggregate`

---

## Contacts & References

| Resource | Link |
|----------|------|
| JMeter User Manual | https://jmeter.apache.org/usermanual/ |
| JMeter Best Practices | https://jmeter.apache.org/usermanual/best-practices.html |
| JMeter Component Reference | https://jmeter.apache.org/usermanual/component_reference.html |
| JMeter Functions Reference | https://jmeter.apache.org/usermanual/functions.html |
