#!/usr/bin/env python3
"""
analyze_results.py — AEP Performance Results Analyzer

Generates a professional, light-themed HTML report with executive summary,
KPI scorecards, compact charts, and a plain-English transaction table
suitable for leadership and QA teams alike.

USAGE
-----
Single run:
    python3 analyze_results.py results/<run>/results.jtl

With options:
    python3 analyze_results.py results/<run>/results.jtl \\
        --sla 3000 --error-rate 1.0 --env qa --users 10 \\
        --html results/<run>/summary.html

Aggregate across multiple runs:
    python3 analyze_results.py --aggregate run1.jtl run2.jtl run3.jtl \\
        --sla 3000 --env qa --users 10 --html output/summary.html

EXIT CODES
----------
  0  All transactions passed
  1  One or more violations
  2  Input error
"""

from __future__ import annotations

import argparse
import csv
import html as html_mod
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import NamedTuple


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

class TxStats(NamedTuple):
    label: str
    samples: int
    errors: int
    avg_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    throughput: float
    error_rate: float
    sla_ok: bool
    err_ok: bool

    @property
    def passed(self) -> bool:
        return self.sla_ok and self.err_ok

    @property
    def short_label(self) -> str:
        return re.sub(r"^TC_\d+_", "", self.label).replace("_", " ")


# ─────────────────────────────────────────────────────────────────────────────
# Parsing & statistics
# ─────────────────────────────────────────────────────────────────────────────

def parse_jtl(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _pct(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def build_stats(rows: list[dict], sla_ms: int, max_err: float) -> tuple[list[TxStats], TxStats]:
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_label[r.get("label", "unknown")].append(r)

    ts_vals = [int(r["timeStamp"]) for r in rows if r.get("timeStamp")]
    duration_s = (max(ts_vals) - min(ts_vals)) / 1000 if len(ts_vals) > 1 else 1

    def _stat(label: str, sample_rows: list[dict]) -> TxStats:
        elapsed = [int(r["elapsed"]) for r in sample_rows if r.get("elapsed")]
        errors  = sum(1 for r in sample_rows if r.get("success", "true").lower() == "false")
        n       = len(sample_rows)
        err_pct = (errors / n * 100) if n else 0.0
        return TxStats(
            label      = label,
            samples    = n,
            errors     = errors,
            avg_ms     = mean(elapsed)     if elapsed else 0.0,
            median_ms  = median(elapsed)   if elapsed else 0.0,
            p90_ms     = _pct(elapsed, 90) if elapsed else 0.0,
            p95_ms     = _pct(elapsed, 95) if elapsed else 0.0,
            p99_ms     = _pct(elapsed, 99) if elapsed else 0.0,
            min_ms     = min(elapsed)      if elapsed else 0.0,
            max_ms     = max(elapsed)      if elapsed else 0.0,
            throughput = n / duration_s,
            error_rate = err_pct,
            sla_ok     = _pct(elapsed, 90) <= sla_ms if elapsed else True,
            err_ok     = err_pct <= max_err,
        )

    tx = [_stat(lbl, sr) for lbl, sr in sorted(by_label.items()) if lbl.startswith("TC_")]
    return tx, _stat("OVERALL", rows)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jlist(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _perf_label(p90: float, sla: int) -> tuple[str, str]:
    r = p90 / sla if sla else 1
    if r <= 0.50: return "Excellent", "excellent"
    if r <= 0.75: return "Good",      "good"
    if r <= 1.00: return "Fair",      "fair"
    return "Needs Attention", "poor"


# ─────────────────────────────────────────────────────────────────────────────
# Log parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_log(path: Path | None) -> list[dict]:
    """Return list of {ts, level, source, message} dicts from jmeter.log."""
    if not path or not path.exists():
        return []
    entries = []
    pattern = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+(INFO|WARN|ERROR|DEBUG)\s+(\S+):\s+(.*)'
    )
    current: dict | None = None
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            m = pattern.match(line)
            if m:
                if current:
                    entries.append(current)
                current = {
                    "ts":      m.group(1),
                    "level":   m.group(2),
                    "source":  m.group(3),
                    "message": m.group(4),
                }
            elif current:
                current["message"] += "\n" + line
    if current:
        entries.append(current)
    return entries


def _log_html_section(log_path: Path | None) -> str:
    """Build the collapsible debug log section for the HTML report."""
    entries = parse_log(log_path)
    if not entries:
        return ""

    # Buckets: errors/warns always shown; info filtered to useful sources
    errors   = [e for e in entries if e["level"] == "ERROR"]
    warns    = [e for e in entries if e["level"] == "WARN"]
    groovy   = [e for e in entries if e["level"] == "INFO"
                and any(k in e["source"] + e["message"]
                        for k in ("JSR223", "Groovy", "ScriptEngine",
                                  "TC_17", "PlaceOrder", "EX_", "ExtractFields",
                                  "ExtractSku", "summary"))]
    startup  = [e for e in entries if e["level"] == "INFO"
                and "JMeter" in e["source"] and "Setting JMeter property" in e["message"]]

    def _rows(items: list[dict], level_cls: str) -> str:
        if not items:
            return '<tr><td colspan="3" style="color:var(--text-3);font-style:italic;padding:10px">No entries</td></tr>'
        out = ""
        for e in items:
            src_short = e["source"].split(".")[-1]
            msg_escaped = html_mod.escape(e["message"])
            # wrap long lines
            msg_html = f'<span style="white-space:pre-wrap;font-family:var(--mono);font-size:11px">{msg_escaped}</span>'
            out += f"""<tr>
              <td style="white-space:nowrap;color:var(--text-3);font-size:10px;font-family:var(--mono);padding:5px 8px">{html_mod.escape(e["ts"])}</td>
              <td style="padding:5px 8px"><span class="log-badge log-{level_cls}">{e["level"]}</span></td>
              <td style="padding:5px 8px;color:var(--text-3);font-size:10px">{html_mod.escape(src_short)}</td>
              <td style="padding:5px 8px">{msg_html}</td>
            </tr>"""
        return out

    def _panel(title: str, icon: str, items: list[dict], level_cls: str,
               open_attr: str = "") -> str:
        count = len(items)
        count_badge_cls = "log-error-cnt" if level_cls == "error" else \
                          "log-warn-cnt"  if level_cls == "warn"  else "log-info-cnt"
        return f"""
        <details {open_attr} class="log-details">
          <summary class="log-summary">
            <span class="log-summary-icon">{icon}</span>
            <span class="log-summary-title">{title}</span>
            <span class="log-count {count_badge_cls}">{count}</span>
            <span class="log-chevron">▶</span>
          </summary>
          <div class="log-table-wrap">
            <table class="log-table">
              <thead><tr>
                <th style="width:160px">Timestamp</th>
                <th style="width:60px">Level</th>
                <th style="width:120px">Source</th>
                <th>Message</th>
              </tr></thead>
              <tbody>{_rows(items, level_cls)}</tbody>
            </table>
          </div>
        </details>"""

    err_open  = 'open' if errors else ''
    warn_open = 'open' if not errors and warns else ''

    total_log_lines = len(entries)

    return f"""
<!-- ══════════════════════════════════════════════════════════════════════════
     DEBUG LOGS
════════════════════════════════════════════════════════════════════════════ -->
<section class="section">
  <h2 class="section-title">
    <span class="section-icon">🪵</span>Debug Logs
    <span style="font-size:10px;font-weight:400;color:var(--text-3);margin-left:8px">
      {total_log_lines} total log lines · click a panel to expand
    </span>
  </h2>
  <div class="log-panels">
    {_panel("Errors", "🔴", errors, "error", err_open)}
    {_panel("Warnings", "🟡", warns, "warn", warn_open)}
    {_panel("Groovy / JSR223 Script Output", "🟢", groovy, "info")}
    {_panel("JMeter Startup &amp; Configuration", "🔵", startup, "info")}
  </div>
</section>"""


# ─────────────────────────────────────────────────────────────────────────────
# Terminal output
# ─────────────────────────────────────────────────────────────────────────────

R = "\033[0m"; BOLD = "\033[1m"; GRN = "\033[32m"
RED = "\033[31m"; CYN = "\033[36m"; DIM = "\033[2m"


def print_terminal(
    tx: list[TxStats], ov: TxStats, *,
    sla_ms: int, max_err: float, env: str, run: str, users: int,
) -> bool:
    div = "─" * 112
    ts  = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{BOLD}{div}{R}")
    print(f"{BOLD}  AEP Performance Results  │  Env: {env.upper()}  │  Users: {users}  │  {run}  │  {ts}{R}")
    print(f"{DIM}  SLA: response time ≤ {sla_ms} ms for 90% of users  │  Max error rate: {max_err}%{R}")
    print(f"{BOLD}{div}{R}")
    print(f"{CYN}  {'Test Case':<40}  {'Requests':>8}  {'Avg (ms)':>9}  {'90% (ms)':>9}  {'95% (ms)':>9}  {'Errors':>7}  Result{R}")
    print(f"{BOLD}{div}{R}")

    all_pass = True
    for s in tx:
        p90c = f"{RED}{s.p90_ms:>9.0f}{R}" if not s.sla_ok else f"{s.p90_ms:>9.0f}"
        errc = f"{RED}{s.error_rate:>7.2f}{R}" if not s.err_ok else f"{s.error_rate:>7.2f}"
        stat = f"{GRN}  PASS{R}" if s.passed else f"{RED}  FAIL{R}"
        if not s.passed:
            all_pass = False
        print(f"  {s.label[:40]:<40}  {s.samples:>8}  {s.avg_ms:>9.0f}  {p90c}  {s.p95_ms:>9.0f}  {errc}  {stat}")

    print(f"{BOLD}{div}{R}")
    op90  = f"{RED}{ov.p90_ms:>9.0f}{R}" if not ov.sla_ok else f"{GRN}{ov.p90_ms:>9.0f}{R}"
    oerr  = f"{RED}{ov.error_rate:>7.2f}{R}" if not ov.err_ok else f"{GRN}{ov.error_rate:>7.2f}{R}"
    ostat = f"{GRN}  PASS{R}" if ov.passed else f"{RED}  FAIL{R}"
    if not ov.passed:
        all_pass = False
    print(f"  {BOLD}{'OVERALL':<40}{R}  {ov.samples:>8}  {ov.avg_ms:>9.0f}  {op90}  {ov.p95_ms:>9.0f}  {oerr}  {ostat}")
    print(f"{BOLD}{div}{R}\n")
    v = f"{GRN}{BOLD}ALL TESTS PASSED{R}" if all_pass else f"{RED}{BOLD}VIOLATIONS DETECTED{R}"
    print(f"  Verdict: {v}  │  Throughput: {ov.throughput:.2f} req/s  │  Min: {ov.min_ms:.0f} ms  │  Max: {ov.max_ms:.0f} ms\n")
    return all_pass


# ─────────────────────────────────────────────────────────────────────────────
# HTML Report
# ─────────────────────────────────────────────────────────────────────────────

def write_html(
    tx: list[TxStats],
    ov: TxStats,
    *,
    out: Path,
    sla_ms: int,
    max_err: float,
    env: str,
    run: str,
    users: int,
    run_overalls: list[tuple[str, TxStats]] | None = None,
    log_path: Path | None = None,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    passed_count = sum(1 for s in tx if s.passed)
    failed_count = len(tx) - passed_count
    total_tc     = len(tx)
    ts_now       = datetime.now(tz=timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    perf_text, perf_cls = _perf_label(ov.p90_ms, sla_ms)
    verdict_text = "PASS" if ov.passed else "FAIL"
    verdict_cls  = "pass" if ov.passed else "fail"

    # ── Chart data ───────────────────────────────────────────────────────────
    tc_labels = _jlist([f'"{s.short_label}"' for s in tx])
    tc_p90    = _jlist([f"{s.p90_ms:.0f}"    for s in tx])
    tc_avg    = _jlist([f"{s.avg_ms:.0f}"    for s in tx])
    tc_colors = _jlist(['"#16a34a"' if s.sla_ok else '"#dc2626"' for s in tx])
    tc_avg_colors = _jlist(['"#3b82f6"' if s.sla_ok else '"#f97316"' for s in tx])

    trend_labels = _jlist([f'"{r}"'           for r, _ in (run_overalls or [])])
    trend_p90    = _jlist([f"{s.p90_ms:.0f}"  for _, s in (run_overalls or [])])
    trend_avg    = _jlist([f"{s.avg_ms:.0f}"  for _, s in (run_overalls or [])])

    # ── Table rows ───────────────────────────────────────────────────────────
    table_rows = ""
    for i, s in enumerate(tx):
        pt, pc   = _perf_label(s.p90_ms, sla_ms)
        badge    = f'<span class="badge {"pass" if s.passed else "fail"}">{"✓ Pass" if s.passed else "✗ Fail"}</span>'
        rating   = f'<span class="rating {pc}">{pt}</span>'
        p90_cls  = " red-val" if not s.sla_ok else ""
        err_cls  = " red-val" if not s.err_ok else ""
        row_cls  = " fail-row" if not s.passed else ""
        health   = f'<div class="health-bar"><div class="health-fill {"hf-good" if s.sla_ok else "hf-bad"}" style="width:{min(s.p90_ms/sla_ms*100,100):.0f}%"></div></div>'
        table_rows += f"""
        <tr class="{row_cls}">
          <td class="num tc-num">{i+1:02d}</td>
          <td class="label-cell" title="{s.label}">{s.short_label}</td>
          <td class="num">{s.samples}</td>
          <td class="num{err_cls}">{s.errors}</td>
          <td class="num">{s.avg_ms:.0f}</td>
          <td class="num">{s.median_ms:.0f}</td>
          <td class="num{p90_cls}">{s.p90_ms:.0f}{health}</td>
          <td class="num">{s.p95_ms:.0f}</td>
          <td class="num">{s.p99_ms:.0f}</td>
          <td class="num{err_cls}">{s.error_rate:.2f}%</td>
          <td>{rating}</td>
          <td>{badge}</td>
        </tr>"""

    # ── Run comparison ───────────────────────────────────────────────────────
    trend_rows = ""
    if run_overalls and len(run_overalls) > 1:
        for rl, rs in run_overalls:
            pt, pc = _perf_label(rs.p90_ms, sla_ms)
            b  = f'<span class="badge {"pass" if rs.passed else "fail"}">{"✓ Pass" if rs.passed else "✗ Fail"}</span>'
            r2 = f'<span class="rating {pc}">{pt}</span>'
            trend_rows += f"""
            <tr>
              <td><strong>{rl}</strong></td>
              <td class="num">{rs.samples}</td>
              <td class="num">{rs.avg_ms:.0f}</td>
              <td class="num {"red-val" if not rs.sla_ok else ""}">{rs.p90_ms:.0f}</td>
              <td class="num">{rs.error_rate:.2f}%</td>
              <td class="num">{rs.throughput:.2f}</td>
              <td>{r2}</td>
              <td>{b}</td>
            </tr>"""

    trend_section = ""
    trend_chart_js = ""
    if run_overalls and len(run_overalls) > 1:
        trend_section = f"""
        <section class="section">
          <h2 class="section-title">
            <span class="section-icon">📈</span>Run-over-Run Comparison
          </h2>
          <div class="charts-row">
            <div class="chart-card" style="flex:1">
              <div class="chart-header">
                <span class="chart-title">Response Time Trend Across Runs</span>
                <span class="chart-sub">Tracking consistency across repeated test iterations</span>
              </div>
              <canvas id="trendChart" height="100"></canvas>
            </div>
          </div>
          <div class="table-wrap" style="margin-top:20px">
            <table>
              <thead><tr>
                <th>Run</th><th class="num">Requests</th>
                <th class="num">Avg Speed</th>
                <th class="num">Speed (90% of Users)</th>
                <th class="num">Failure Rate</th>
                <th class="num">Requests/sec</th>
                <th>Rating</th><th>Result</th>
              </tr></thead>
              <tbody>{trend_rows}</tbody>
            </table>
          </div>
        </section>"""
        trend_chart_js = f"""
        new Chart(document.getElementById('trendChart'), {{
          type: 'line',
          data: {{
            labels: {trend_labels},
            datasets: [
              {{ label: 'Speed — 90% of users (ms)', data: {trend_p90},
                 borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.08)',
                 tension: 0.35, fill: true, pointRadius: 5, pointHoverRadius: 7 }},
              {{ label: 'Average Speed (ms)', data: {trend_avg},
                 borderColor: '#16a34a', backgroundColor: 'transparent',
                 tension: 0.35, fill: false, pointRadius: 4, borderDash: [4,3] }}
            ]
          }},
          options: {{
            ...lineOpts,
            plugins: {{ ...lineOpts.plugins,
              annotation: {{ annotations: {{ sla: {{
                type:'line', yMin:{sla_ms}, yMax:{sla_ms},
                borderColor:'rgba(220,38,38,0.5)', borderWidth:1.5, borderDash:[6,4],
                label:{{ content:'Target limit {sla_ms}ms', display:true, position:'end',
                         color:'#dc2626', font:{{size:10}}, backgroundColor:'transparent' }}
              }} }} }}
            }}
          }}
        }});"""

    # ── Log section ──────────────────────────────────────────────────────────
    log_section_html = _log_html_section(log_path)

    # ── Status banner data ───────────────────────────────────────────────────
    verdict_icon = "✅" if ov.passed else "❌"
    verdict_bg   = "#f0fdf4" if ov.passed else "#fef2f2"
    verdict_bdr  = "#16a34a" if ov.passed else "#dc2626"

    failed_cases = [s for s in tx if not s.passed]
    action_html  = ""
    if ov.passed:
        action_html = (
            '<div class="status-action status-ok">'
            '<strong>✓ No action required.</strong> '
            'All test scenarios are performing within the agreed response time target.'
            '</div>'
        )
    else:
        rows_html = "".join(
            f'<li><strong>{s.short_label}</strong> — '
            f'{"response time " + str(int(s.p90_ms)) + " ms (target " + str(sla_ms) + " ms)" if not s.sla_ok else ""}'
            f'{"" if s.sla_ok or s.err_ok else " · "}'
            f'{"failure rate " + f"{s.error_rate:.1f}%" + " (limit " + str(max_err) + "%)" if not s.err_ok else ""}'
            f'</li>'
            for s in failed_cases
        )
        action_html = (
            f'<div class="status-action status-fail">'
            f'<strong>⚠ Action Required — {failed_count} scenario(s) need attention:</strong>'
            f'<ul>{rows_html}</ul>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AEP Performance Report — {env.upper()} · {run}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ── Reset ───────────────────────────────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}

/* ── Design tokens ───────────────────────────────────────────────────────── */
:root{{
  --bg:       #f8fafc;
  --surface:  #ffffff;
  --surface2: #f1f5f9;
  --border:   #e2e8f0;
  --border2:  #cbd5e1;
  --text:     #0f172a;
  --text-2:   #475569;
  --text-3:   #94a3b8;
  --blue:     #2563eb;
  --blue-l:   #dbeafe;
  --green:    #16a34a;
  --green-l:  #dcfce7;
  --red:      #dc2626;
  --red-l:    #fee2e2;
  --amber:    #d97706;
  --amber-l:  #fef3c7;
  --purple:   #7c3aed;
  --purple-l: #ede9fe;
  --font:     'Segoe UI',system-ui,-apple-system,sans-serif;
  --mono:     'Cascadia Code','Fira Code',Consolas,monospace;
  --radius:   10px;
  --shadow:   0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.05);
  --shadow-md:0 4px 6px rgba(0,0,0,.07),0 2px 4px rgba(0,0,0,.05);
}}

/* ── Base ────────────────────────────────────────────────────────────────── */
body{{background:var(--bg);color:var(--text);font-family:var(--font);
     font-size:13px;line-height:1.6;}}
a{{color:var(--blue);text-decoration:none}}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header{{
  background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 60%,#1e3a5f 100%);
  padding:28px 40px 24px;
  color:#fff;
}}
.header-top{{
  display:flex;align-items:flex-start;
  justify-content:space-between;flex-wrap:wrap;gap:16px;
}}
.brand{{display:flex;align-items:center;gap:14px}}
.brand-logo{{
  width:42px;height:42px;
  background:rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.3);
  border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;font-weight:900;
}}
.brand-name{{font-size:19px;font-weight:700;letter-spacing:-.01em}}
.brand-sub {{font-size:12px;color:rgba(255,255,255,.65);margin-top:2px}}
.verdict-pill{{
  display:flex;align-items:center;gap:8px;
  padding:8px 18px;border-radius:20px;
  font-size:14px;font-weight:700;letter-spacing:.04em;
  backdrop-filter:blur(4px);
}}
.verdict-pill.pass{{background:rgba(22,163,74,.2);border:1.5px solid rgba(74,222,128,.5);color:#4ade80}}
.verdict-pill.fail{{background:rgba(220,38,38,.2);border:1.5px solid rgba(248,113,113,.5);color:#f87171}}
.header-chips{{
  display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;
  padding-top:16px;border-top:1px solid rgba(255,255,255,.15);
}}
.chip{{
  background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  border-radius:20px;padding:3px 12px;font-size:11px;color:rgba(255,255,255,.85);
}}
.chip strong{{color:#fff}}

/* ── Layout ──────────────────────────────────────────────────────────────── */
.container{{max-width:1360px;margin:0 auto;padding:28px 40px}}
.section{{margin-bottom:36px}}
.section-title{{
  font-size:13px;font-weight:700;color:var(--text-2);
  text-transform:uppercase;letter-spacing:.09em;
  margin-bottom:14px;
  display:flex;align-items:center;gap:8px;
}}
.section-icon{{font-size:15px}}

/* ── Status banner ───────────────────────────────────────────────────────── */
.status-banner{{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow);
  display:flex;align-items:stretch;
  overflow:hidden;
  margin-bottom:28px;
}}
.status-left{{
  background:{verdict_bg};
  border-right:1px solid {verdict_bdr}33;
  padding:20px 24px;
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:6px;min-width:140px;
}}
.status-verdict{{
  font-size:22px;font-weight:800;color:{verdict_bdr};letter-spacing:.03em;
}}
.status-icon{{font-size:28px;line-height:1}}
.status-sub{{font-size:11px;color:{verdict_bdr};opacity:.75;text-align:center}}
.status-right{{
  padding:18px 24px;flex:1;
  display:flex;flex-direction:column;gap:10px;justify-content:center;
}}
.status-meta{{
  display:flex;flex-wrap:wrap;gap:6px 24px;
}}
.status-item{{font-size:12px;color:var(--text-2)}}
.status-item strong{{color:var(--text)}}
.status-action{{
  padding:10px 14px;border-radius:7px;font-size:12px;line-height:1.65;
}}
.status-action ul{{margin:.4em 0 0 1.2em}}
.status-action li{{margin-bottom:2px}}
.status-ok{{
  background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;
}}
.status-fail{{
  background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;
}}

/* ── KPI + Charts combined layout ───────────────────────────────────────── */
.dashboard-row{{
  display:grid;
  grid-template-columns:340px minmax(0,1fr);
  gap:14px;
  align-items:start;
}}
@media(max-width:900px){{
  .dashboard-row{{grid-template-columns:1fr}}
}}
/* ── KPI grid ────────────────────────────────────────────────────────────── */
.kpi-grid{{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px;
}}
.kpi{{
  padding:12px 13px 10px !important;
}}
.kpi-value{{
  font-size:20px !important;
}}
.kpi{{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:16px 16px 14px;
  box-shadow:var(--shadow);
  position:relative;overflow:hidden;
}}
.kpi::after{{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  border-radius:var(--radius) var(--radius) 0 0;
  background:var(--blue);
}}
.kpi.k-green::after{{background:var(--green)}}
.kpi.k-red::after  {{background:var(--red)}}
.kpi.k-amber::after{{background:var(--amber)}}
.kpi.k-purple::after{{background:var(--purple)}}
.kpi-label{{font-size:11px;color:var(--text-3);text-transform:uppercase;
            letter-spacing:.06em;margin-bottom:6px}}
.kpi-value{{font-size:24px;font-weight:700;line-height:1;color:var(--text)}}
.kpi-value.v-green{{color:var(--green)}}
.kpi-value.v-red  {{color:var(--red)}}
.kpi-value.v-blue {{color:var(--blue)}}
.kpi-value.v-amber{{color:var(--amber)}}
.kpi-sub  {{font-size:11px;color:var(--text-3);margin-top:5px}}
.kpi-hint {{font-size:10px;color:var(--text-3);margin-top:3px;font-style:italic}}

/* ── Charts ──────────────────────────────────────────────────────────────── */
.charts-row{{display:flex;gap:14px;flex-wrap:wrap}}
.chart-card{{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:16px 18px;
  box-shadow:var(--shadow);
}}
.chart-header{{margin-bottom:12px}}
.chart-title{{font-size:12px;font-weight:700;color:var(--text-2)}}
.chart-sub  {{font-size:11px;color:var(--text-3);margin-top:2px}}
.donut-card{{width:200px;flex-shrink:0}}
.donut-wrap{{display:flex;flex-direction:column;align-items:center;gap:12px;padding-top:4px}}
.donut-legend{{width:100%}}
.legend-row{{
  display:flex;align-items:center;justify-content:space-between;
  font-size:11px;padding:3px 0;
}}
.legend-dot{{
  width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-right:6px;
}}
.legend-label{{display:flex;align-items:center;color:var(--text-2)}}
.legend-val{{font-weight:700;color:var(--text)}}

/* ── Table ───────────────────────────────────────────────────────────────── */
.table-wrap{{overflow-x:auto;border-radius:var(--radius);
             border:1px solid var(--border);box-shadow:var(--shadow)}}
table{{width:100%;border-collapse:collapse}}
thead th{{
  background:var(--surface2);
  padding:9px 11px;text-align:left;
  font-size:10.5px;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;
  color:var(--text-2);
  border-bottom:1.5px solid var(--border2);
  white-space:nowrap;
}}
thead th.num{{text-align:right}}
tbody tr{{border-bottom:1px solid var(--border);transition:background .1s}}
tbody tr:hover{{background:#f8fafc}}
tbody tr.fail-row{{background:#fff8f8}}
tbody tr.fail-row:hover{{background:#fef2f2}}
td{{padding:8px 11px;white-space:nowrap;font-size:12px}}
td.num{{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono)}}
td.tc-num{{color:var(--text-3);font-size:11px;font-family:var(--mono)}}
td.label-cell{{max-width:210px;overflow:hidden;text-overflow:ellipsis;font-weight:500}}
tfoot td{{
  background:var(--surface2);font-weight:700;
  border-top:2px solid var(--border2);padding:9px 11px;font-size:12px;
}}
tfoot td.num{{text-align:right}}
.red-val{{color:var(--red);font-weight:700}}

/* ── Health bar ──────────────────────────────────────────────────────────── */
.health-bar{{
  height:3px;background:var(--border);border-radius:2px;margin-top:4px;width:64px;
}}
.health-fill{{height:100%;border-radius:2px;transition:width .3s}}
.hf-good{{background:var(--green)}}
.hf-bad {{background:var(--red)}}

/* ── Badges & ratings ────────────────────────────────────────────────────── */
.badge{{
  display:inline-block;padding:2px 9px;border-radius:9999px;
  font-size:10px;font-weight:700;letter-spacing:.04em;
}}
.badge.pass{{background:var(--green-l);color:var(--green)}}
.badge.fail{{background:var(--red-l);color:var(--red)}}
.rating{{
  display:inline-block;padding:2px 7px;border-radius:4px;
  font-size:10px;font-weight:600;
}}
.rating.excellent{{background:var(--green-l);color:var(--green)}}
.rating.good     {{background:var(--blue-l);color:var(--blue)}}
.rating.fair     {{background:var(--amber-l);color:var(--amber)}}
.rating.poor     {{background:var(--red-l);color:var(--red)}}

/* ── Metrics guide ───────────────────────────────────────────────────────── */
.metrics-grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;
}}
.metric-card{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 15px;box-shadow:var(--shadow);
}}
.metric-name{{font-weight:700;color:var(--text);font-size:12px;margin-bottom:4px;
              display:flex;align-items:center;gap:6px}}
.metric-tag{{
  font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px;
  text-transform:uppercase;letter-spacing:.05em;
}}
.metric-tag.sla-gate{{background:var(--blue-l);color:var(--blue)}}
.metric-def{{font-size:11px;color:var(--text-2);line-height:1.55}}

/* ── Footer ──────────────────────────────────────────────────────────────── */
footer{{
  background:var(--surface);border-top:1px solid var(--border);
  padding:16px 40px;
  display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:8px;font-size:11px;color:var(--text-3);
}}

/* ── Print ───────────────────────────────────────────────────────────────── */
@media print{{
  .page-header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  body{{font-size:11px}}
}}

/* ── Debug log panels ────────────────────────────────────────────────────── */
.log-panels{{display:flex;flex-direction:column;gap:8px}}
.log-details{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;
}}
.log-details[open] .log-chevron{{transform:rotate(90deg)}}
.log-summary{{
  display:flex;align-items:center;gap:10px;
  padding:11px 16px;cursor:pointer;
  user-select:none;list-style:none;
  font-size:12px;font-weight:600;color:var(--text);
}}
.log-summary::-webkit-details-marker{{display:none}}
.log-summary:hover{{background:var(--surface2)}}
.log-summary-icon{{font-size:13px;line-height:1}}
.log-summary-title{{flex:1}}
.log-count{{
  display:inline-block;padding:1px 8px;border-radius:9999px;
  font-size:10px;font-weight:700;
}}
.log-error-cnt{{background:var(--red-l);color:var(--red)}}
.log-warn-cnt {{background:var(--amber-l);color:var(--amber)}}
.log-info-cnt {{background:var(--blue-l);color:var(--blue)}}
.log-chevron{{font-size:9px;color:var(--text-3);transition:transform .2s;margin-left:4px}}
.log-table-wrap{{
  overflow-x:auto;border-top:1px solid var(--border);
  max-height:420px;overflow-y:auto;
}}
.log-table{{width:100%;border-collapse:collapse;font-size:11px}}
.log-table thead th{{
  background:var(--surface2);padding:7px 8px;
  text-align:left;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;color:var(--text-2);
  border-bottom:1px solid var(--border2);position:sticky;top:0;
}}
.log-table tbody tr{{border-bottom:1px solid var(--border)}}
.log-table tbody tr:hover{{background:#f8fafc}}
.log-badge{{
  display:inline-block;padding:1px 6px;border-radius:3px;
  font-size:9px;font-weight:700;font-family:var(--mono);letter-spacing:.04em;
}}
.log-error{{background:var(--red-l);color:var(--red)}}
.log-warn {{background:var(--amber-l);color:var(--amber)}}
.log-info {{background:var(--blue-l);color:var(--blue)}}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media(max-width:860px){{
  .exec-grid{{grid-template-columns:1fr}}
  .container{{padding:16px}}
  .page-header{{padding:20px 16px}}
  footer{{padding:14px 16px}}
}}
</style>
</head>
<body>

<!-- ══════════════════════════════════════════════════════════════════════════
     PAGE HEADER
════════════════════════════════════════════════════════════════════════════ -->
<header class="page-header">
  <div class="header-top">
    <div class="brand">
      <div class="brand-logo">A</div>
      <div>
        <div class="brand-name">AEP ECommerce — Performance Report</div>
        <div class="brand-sub">Automated Quality Assurance · Performance Test Results</div>
      </div>
    </div>
    <div class="verdict-pill {verdict_cls}">
      {verdict_icon}&nbsp; Overall Result: {verdict_text}
    </div>
  </div>
  <div class="header-chips">
    <span class="chip">Environment: <strong>{env.upper()}</strong></span>
    <span class="chip">Run: <strong>{run}</strong></span>
    <span class="chip">Simulated Users: <strong>{users}</strong></span>
    <span class="chip">Test Cases: <strong>{total_tc}</strong></span>
    <span class="chip">Response Time Target: <strong>≤ {sla_ms} ms</strong></span>
    <span class="chip">Generated: <strong>{ts_now}</strong></span>
  </div>
</header>

<div class="container">

<!-- ══════════════════════════════════════════════════════════════════════════
     STATUS BANNER
════════════════════════════════════════════════════════════════════════════ -->
<div class="status-banner">
  <div class="status-left">
    <div class="status-icon">{verdict_icon}</div>
    <div class="status-verdict">{verdict_text}</div>
    <div class="status-sub">{passed_count} of {total_tc} passed</div>
  </div>
  <div class="status-right">
    <div class="status-meta">
      <div class="status-item">Environment: <strong>{env.upper()}</strong></div>
      <div class="status-item">Run: <strong>{run}</strong></div>
      <div class="status-item">Simulated Users: <strong>{users}</strong></div>
      <div class="status-item">Test Date: <strong>{ts_now}</strong></div>
      <div class="status-item">Avg Response: <strong>{ov.avg_ms:.0f} ms</strong></div>
      <div class="status-item">Speed (90% of users): <strong style="color:{"var(--green)" if ov.sla_ok else "var(--red)"}">{ov.p90_ms:.0f} ms</strong> <span style="color:var(--text-3);font-size:11px">(target ≤ {sla_ms} ms)</span></div>
      <div class="status-item">Failure Rate: <strong style="color:{"var(--green)" if ov.err_ok else "var(--red)"}">{ov.error_rate:.2f}%</strong> <span style="color:var(--text-3);font-size:11px">(limit {max_err}%)</span></div>
      <div class="status-item">Throughput: <strong>{ov.throughput:.1f} req/s</strong></div>
    </div>
    {action_html}
  </div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     SCORECARDS + CHARTS
════════════════════════════════════════════════════════════════════════════ -->
<section class="section">
  <h2 class="section-title">
    <span class="section-icon">📊</span>Performance Overview
  </h2>
  <div class="dashboard-row">

    <!-- Left: KPI scorecards 2-col grid -->
    <div class="kpi-grid">

      <div class="kpi k-{'green' if ov.passed else 'red'}">
        <div class="kpi-label">Test Result</div>
        <div class="kpi-value v-{'green' if ov.passed else 'red'}">{verdict_text}</div>
        <div class="kpi-sub">{passed_count} of {total_tc} passed</div>
      </div>

      <div class="kpi k-{'green' if ov.err_ok else 'red'}">
        <div class="kpi-label">Failure Rate</div>
        <div class="kpi-value v-{'green' if ov.err_ok else 'red'}">{ov.error_rate:.2f}%</div>
        <div class="kpi-sub">Limit: {max_err}% {"✓" if ov.err_ok else "✗"}</div>
        <div class="kpi-hint">% of requests that errored</div>
      </div>

      <div class="kpi k-blue">
        <div class="kpi-label">Avg Response</div>
        <div class="kpi-value v-blue">{ov.avg_ms:.0f} ms</div>
        <div class="kpi-sub">Median: {ov.median_ms:.0f} ms</div>
        <div class="kpi-hint">Server average response time</div>
      </div>

      <div class="kpi k-{'green' if ov.sla_ok else 'red'}">
        <div class="kpi-label">Speed — 90% Users</div>
        <div class="kpi-value v-{'green' if ov.sla_ok else 'red'}">{ov.p90_ms:.0f} ms</div>
        <div class="kpi-sub">Target ≤ {sla_ms} ms {"✓" if ov.sla_ok else "✗"}</div>
        <div class="kpi-hint">9 in 10 users this fast or better</div>
      </div>

      <div class="kpi k-blue">
        <div class="kpi-label">Speed — 95% Users</div>
        <div class="kpi-value v-blue">{ov.p95_ms:.0f} ms</div>
        <div class="kpi-sub">19 in 20 users</div>
        <div class="kpi-hint">Near worst-case experience</div>
      </div>

      <div class="kpi k-purple">
        <div class="kpi-label">Speed — 99% Users</div>
        <div class="kpi-value" style="color:var(--purple)">{ov.p99_ms:.0f} ms</div>
        <div class="kpi-sub">99 in 100 users</div>
        <div class="kpi-hint">Worst-case tail latency</div>
      </div>

      <div class="kpi k-blue">
        <div class="kpi-label">Throughput</div>
        <div class="kpi-value v-blue">{ov.throughput:.1f}</div>
        <div class="kpi-sub">Requests / second</div>
        <div class="kpi-hint">Higher = more server capacity</div>
      </div>

      <div class="kpi k-amber">
        <div class="kpi-label">Response Range</div>
        <div class="kpi-value v-amber" style="font-size:18px">{ov.min_ms:.0f}–{ov.max_ms:.0f} ms</div>
        <div class="kpi-sub">Min – Max</div>
        <div class="kpi-hint">Consistency of response times</div>
      </div>

    </div>

    <!-- Right: donut + P90 bar stacked -->
    <div style="display:flex;flex-direction:column;gap:10px;min-width:0">

      <!-- Donut inline with legend -->
      <div class="chart-card" style="padding:14px 16px">
        <div class="chart-title" style="margin-bottom:10px">Scenarios Passed vs Failed</div>
        <div style="display:flex;align-items:center;gap:16px">
          <div style="width:90px;height:90px;flex-shrink:0;position:relative">
            <canvas id="donutChart"></canvas>
          </div>
          <div style="flex:1;font-size:12px">
            <div class="legend-row">
              <div class="legend-label"><div class="legend-dot" style="background:#16a34a"></div>Passed</div>
              <div class="legend-val" style="color:var(--green);font-size:16px;font-weight:800">{passed_count}</div>
            </div>
            <div class="legend-row">
              <div class="legend-label"><div class="legend-dot" style="background:#dc2626"></div>Failed</div>
              <div class="legend-val" style="color:var(--red);font-size:16px;font-weight:800">{failed_count}</div>
            </div>
            <div class="legend-row" style="margin-top:6px;padding-top:6px;border-top:1px solid var(--border)">
              <div class="legend-label" style="font-weight:700;color:var(--text-2)">Pass Rate</div>
              <div class="legend-val" style="font-size:15px;font-weight:800">{f"{passed_count/total_tc*100:.0f}" if total_tc else "0"}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- P90 bar chart — fixed container height -->
      <div class="chart-card" style="padding:14px 16px">
        <div class="chart-title" style="margin-bottom:4px">Response Time — 90% of Users per Scenario (ms)</div>
        <div class="chart-sub" style="margin-bottom:10px">Green = within {sla_ms} ms target · Red = exceeded</div>
        <div style="position:relative;height:200px">
          <canvas id="p90Chart"></canvas>
        </div>
      </div>

    </div>
  </div>
</section>

<!-- ══════════════════════════════════════════════════════════════════════════
     DETAILED RESULTS TABLE
════════════════════════════════════════════════════════════════════════════ -->
<section class="section">
  <h2 class="section-title">
    <span class="section-icon">🔍</span>Detailed Test Results
  </h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Test Scenario</th>
          <th class="num">Requests</th>
          <th class="num">Errors</th>
          <th class="num">Avg Speed</th>
          <th class="num">Typical Speed<br><span style="font-weight:400;font-size:9px">(50% of users)</span></th>
          <th class="num">
            Speed — 90% of Users ★
            <br><span style="font-weight:400;font-size:9px">Target ≤ {sla_ms} ms</span>
          </th>
          <th class="num">Speed — 95%<br><span style="font-weight:400;font-size:9px">of users</span></th>
          <th class="num">Speed — 99%<br><span style="font-weight:400;font-size:9px">of users</span></th>
          <th class="num">Failure Rate</th>
          <th>Rating</th>
          <th>Result</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
      <tfoot>
        <tr>
          <td colspan="2">OVERALL SUMMARY</td>
          <td class="num">{ov.samples}</td>
          <td class="num {'red-val' if ov.errors > 0 else ''}">{ov.errors}</td>
          <td class="num">{ov.avg_ms:.0f}</td>
          <td class="num">{ov.median_ms:.0f}</td>
          <td class="num {'red-val' if not ov.sla_ok else ''}">{ov.p90_ms:.0f}</td>
          <td class="num">{ov.p95_ms:.0f}</td>
          <td class="num">{ov.p99_ms:.0f}</td>
          <td class="num {'red-val' if not ov.err_ok else ''}">{ov.error_rate:.2f}%</td>
          <td><span class="rating {perf_cls}">{perf_text}</span></td>
          <td><span class="badge {verdict_cls}">{"✓ Pass" if ov.passed else "✗ Fail"}</span></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <p style="margin-top:8px;font-size:11px;color:var(--text-3)">
    ★ <strong>Speed — 90% of Users</strong> is the primary pass/fail gate.
    It means 9 out of 10 users received their page or response within that time.
    All values are in milliseconds (ms). 1000 ms = 1 second.
  </p>
</section>

{trend_section}

{log_section_html}

<!-- ══════════════════════════════════════════════════════════════════════════
     METRICS GUIDE
════════════════════════════════════════════════════════════════════════════ -->
<section class="section">
  <h2 class="section-title">
    <span class="section-icon">💡</span>How to Read This Report
  </h2>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-name">
        Average Response Time
      </div>
      <div class="metric-def">
        The mean time the server took to respond across all requests.
        A useful general indicator, but a few very slow requests can pull it upward.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">
        Typical Speed (50% of Users)
      </div>
      <div class="metric-def">
        Half of all users received their response within this time.
        More reliable than the average because it is not affected by outliers.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">
        Speed — 90% of Users
        <span class="metric-tag sla-gate">SLA Gate ★</span>
      </div>
      <div class="metric-def">
        9 out of 10 users received a response within this time.
        This is the primary pass/fail threshold (target: ≤ {sla_ms} ms).
        Industry standard for web performance SLAs.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Speed — 95% of Users</div>
      <div class="metric-def">
        19 out of 20 users were served within this time.
        Reveals near-worst-case experience for the majority.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Speed — 99% of Users</div>
      <div class="metric-def">
        99 out of 100 users were served within this time.
        Shows true worst-case tail latency — important for detecting
        occasional slow spikes.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Failure Rate</div>
      <div class="metric-def">
        Percentage of requests that returned an error or failed validation.
        Target: ≤ {max_err}%. A 0% rate means every single user request succeeded.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Throughput (Requests/sec)</div>
      <div class="metric-def">
        How many requests the system processed every second during the test.
        Higher values indicate the system can handle more concurrent users.
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-name">Performance Rating</div>
      <div class="metric-def">
        <strong style="color:var(--green)">Excellent</strong> — response within 50% of target &nbsp;
        <strong style="color:var(--blue)">Good</strong> — within 75% &nbsp;
        <strong style="color:var(--amber)">Fair</strong> — within 100% &nbsp;
        <strong style="color:var(--red)">Needs Attention</strong> — target exceeded
      </div>
    </div>
  </div>
</section>

</div><!-- /container -->

<!-- ══════════════════════════════════════════════════════════════════════════
     FOOTER
════════════════════════════════════════════════════════════════════════════ -->
<footer>
  <span>AEP Performance Test Suite · Apache JMeter 5.6+</span>
  <span>Response Time Target: ≤ <strong>{sla_ms} ms</strong> for 90% of users &nbsp;·&nbsp; Max Failure Rate: <strong>{max_err}%</strong></span>
  <span>Report generated: <strong>{ts_now}</strong></span>
</footer>

<!-- ══════════════════════════════════════════════════════════════════════════
     CHART.JS
════════════════════════════════════════════════════════════════════════════ -->
<script>
Chart.defaults.color = '#64748b';
Chart.defaults.borderColor = '#e2e8f0';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 11;

const tooltipDefaults = {{
  backgroundColor: '#1e293b',
  borderColor: '#334155',
  borderWidth: 1,
  titleColor: '#f1f5f9',
  bodyColor: '#cbd5e1',
  padding: 10,
  cornerRadius: 6,
}};

const barOpts = {{
  responsive: true,
  plugins: {{
    legend: {{ display: false }},
    tooltip: {{
      ...tooltipDefaults,
      callbacks: {{ label: ctx => ` ${{ctx.parsed.y}} ms` }}
    }}
  }},
  scales: {{
    x: {{
      grid: {{ display: false }},
      ticks: {{ maxRotation: 40, minRotation: 25, font: {{ size: 10 }} }}
    }},
    y: {{
      grid: {{ color: '#f1f5f9' }},
      beginAtZero: true,
      ticks: {{ callback: v => v + ' ms' }}
    }}
  }}
}};

const lineOpts = {{
  responsive: true,
  plugins: {{
    legend: {{ labels: {{ color: '#475569', boxWidth: 12, padding: 14 }} }},
    tooltip: {{ ...tooltipDefaults }}
  }},
  scales: {{
    x: {{ grid: {{ display: false }} }},
    y: {{
      grid: {{ color: '#f1f5f9' }},
      beginAtZero: true,
      ticks: {{ callback: v => v + ' ms' }}
    }}
  }}
}};

// ── Donut ────────────────────────────────────────────────────────────────
new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Passed', 'Failed'],
    datasets: [{{
      data: [{passed_count}, {failed_count}],
      backgroundColor: ['#16a34a', '#dc2626'],
      borderColor: '#ffffff',
      borderWidth: 3,
      hoverOffset: 4
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: true,
    cutout: '72%',
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        ...tooltipDefaults,
        callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.parsed}}` }}
      }}
    }}
  }}
}});

// ── P90 bar ──────────────────────────────────────────────────────────────
new Chart(document.getElementById('p90Chart'), {{
  type: 'bar',
  data: {{
    labels: {tc_labels},
    datasets: [{{
      label: '90% of Users Speed (ms)',
      data: {tc_p90},
      backgroundColor: {tc_colors},
      borderRadius: 3,
      borderSkipped: false,
    }}]
  }},
  options: {{
    ...barOpts,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      ...barOpts.plugins,
      annotation: {{
        annotations: {{
          target: {{
            type: 'line',
            yMin: {sla_ms}, yMax: {sla_ms},
            borderColor: 'rgba(220,38,38,0.5)',
            borderWidth: 1.5,
            borderDash: [5, 4],
            label: {{
              content: 'Target {sla_ms} ms',
              display: true,
              position: 'end',
              color: '#dc2626',
              font: {{ size: 10, weight: '600' }},
              backgroundColor: 'transparent'
            }}
          }}
        }}
      }}
    }}
  }}
}});


{trend_chart_js}
</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("jtl_files", nargs="+", help="JMeter .jtl result file(s)")
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--sla",        type=int,   default=3000)
    parser.add_argument("--error-rate", type=float, default=1.0, dest="error_rate")
    parser.add_argument("--env",        default="qa")
    parser.add_argument("--run",        default="run_01")
    parser.add_argument("--users",      type=int,   default=0)
    parser.add_argument("--html",       default="")
    parser.add_argument("--log",        default="", help="Path to jmeter.log for debug section")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else None
    paths = [Path(f) for f in args.jtl_files]
    for p in paths:
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(2)

    all_passed = True

    if not args.aggregate or len(paths) == 1:
        rows = []
        for p in paths:
            rows.extend(parse_jtl(p))
        if not rows:
            print("ERROR: No data found.", file=sys.stderr)
            sys.exit(2)
        tx, ov = build_stats(rows, args.sla, args.error_rate)
        all_passed = print_terminal(tx, ov, sla_ms=args.sla, max_err=args.error_rate,
                                    env=args.env, run=args.run, users=args.users)
        if args.html:
            write_html(tx, ov, out=Path(args.html), sla_ms=args.sla,
                       max_err=args.error_rate, env=args.env, run=args.run,
                       users=args.users, log_path=log_path)
            print(f"  HTML report → {args.html}")
    else:
        run_overalls: list[tuple[str, TxStats]] = []
        combined: list[dict] = []
        for idx, p in enumerate(paths, 1):
            rl   = f"run_{idx:02d}"
            rows = parse_jtl(p)
            if not rows:
                continue
            combined.extend(rows)
            _, ov = build_stats(rows, args.sla, args.error_rate)
            run_overalls.append((rl, ov))
            print_terminal(*build_stats(rows, args.sla, args.error_rate),
                           sla_ms=args.sla, max_err=args.error_rate,
                           env=args.env, run=rl, users=args.users)

        tx, ov  = build_stats(combined, args.sla, args.error_rate)
        all_passed = ov.passed
        if args.html:
            write_html(tx, ov, out=Path(args.html), sla_ms=args.sla,
                       max_err=args.error_rate, env=args.env,
                       run=f"aggregate_{len(paths)}_runs",
                       users=args.users, run_overalls=run_overalls)
            print(f"  Aggregate HTML report → {args.html}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
