# Changelog

## [1.0.0] — Initial Release

### Added
- `AEP_ECommerce_Performance_TestPlan.jmx` — 16 scenario end-to-end JMeter test plan
- Environment config files: `env.qa.sh`, `env.staging.sh`, `env.prod.sh`
- `run_test.sh` — parameterised runner supporting 5/10/15 users, repeated & parallel runs
- `run_smoke.sh` — quick 1-user sanity check (30 s)
- `run_parallel.sh` — simultaneous multi-tier load (5, 10, 15 users at once)
- `analyze_results.py` — professional HTML report with KPI scorecards, donut chart,
  P90 bar chart, plain-English headers, and leadership-ready status banner
- `test_data.csv` — 10-row parameterised user and product dataset
- `README.md` — full usage guide with examples for all scripts
- `JMETER_REFERENCE.md` — JMeter concepts, metric definitions, and tuning tips
