#!/usr/bin/env python3
"""CLI runner for the NEXUS orchestrated demo.

Runs the demo scenario via API and prints live progress to the terminal.
The demo streams progress via WebSocket; this script polls /demo/status
for the phase log and prints the final report.

Usage:
    make demo
    python scripts/run_demo.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.request import Request, urlopen


def http(
    method: str, url: str, body: dict | None = None, timeout: float = 120.0
) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=timeout) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", 0) or -1
        try:
            raw = e.read().decode()  # type: ignore[attr-defined]
            parsed = json.loads(raw) if raw else {}
            return code, parsed if isinstance(parsed, dict) else {"_error": str(e)}
        except Exception:
            return code, {"_error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NEXUS orchestrated demo")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    # Health check first
    code, health = http("GET", f"{base}/api/v1/health")
    if code != 200:
        print(f"❌ API not reachable at {base} (HTTP {code})")
        return 1
    m = health.get("model_loaded")
    db = health.get("database_connected")
    print(f"🟢 API healthy at {base} (model={m}, db={db})")

    # Start demo (it runs server-side; POST returns when done)
    print("▶ Starting demo scenario…\n")
    code, result = http("POST", f"{base}/api/v1/demo/run", timeout=180.0)
    if code != 200:
        print(f"❌ Demo failed to start: HTTP {code} {result}")
        return 1

    if result.get("status") == "failed":
        print(f"❌ Demo failed: {result.get('error')}")
        return 1

    print(f"✅ Demo completed in {result.get('duration_sec')}s\n")

    # Fetch report
    code, report = http("GET", f"{base}/api/v1/demo/report")
    if code != 200 or report.get("status") == "never_run":
        print("⚠️  No report available")
        return 0

    # Print phase log
    print("── Phase log ──")
    for entry in report.get("phase_log", []):
        print(f"  {entry}")

    # Print predictions accuracy
    preds = report.get("predictions", [])
    if preds:
        correct = sum(1 for p in preds if p.get("got") == p.get("expected"))
        pct = correct / len(preds) * 100
        print(f"\n── Live traffic accuracy: {correct}/{len(preds)} ({pct:.0f}%) ──")

    # Print KPIs
    print("\n── KPIs ──")
    print(f"  Total requests:   {report.get('total_requests')}")
    print(f"  Blocked:          {report.get('blocked')}")
    print(f"  Allowed:          {report.get('allowed')}")
    print(f"  Alerts fired:     {report.get('alerts_fired')}")
    print(f"  Feedback applied: {report.get('feedback_applied')}")

    metrics = report.get("retrain_metrics") or {}
    if metrics:
        acc = metrics.get("accuracy")
        f1 = metrics.get("f1_macro")
        print(f"  Retrain accuracy: {acc}")
        print(f"  Retrain F1-macro: {f1}")

    # Save report copy
    from pathlib import Path

    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = reports_dir / f"demo_{ts}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n📄 Report saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
