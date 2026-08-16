#!/usr/bin/env python3
"""NEXUS Autonomous Verifier — full self-check of all platform functions.

Runs against a live API (default http://localhost:8000) and produces:
  - console summary
  - JSON report (reports/verify_<timestamp>.json)
  - exit code 0 if all critical checks pass, 1 otherwise

Usage:
    make verify
    python scripts/verify.py --base-url http://localhost:8000
    python scripts/verify.py --skip-load   # skip the mini load-burst
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

# ─── Types ────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    duration_ms: float = 0.0
    group: str = "general"
    critical: bool = True


@dataclass
class VerifyReport:
    base_url: str
    started_at: str
    finished_at: str | None = None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.ok)

    @property
    def failed_critical(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok and c.critical]

    @property
    def healthy(self) -> bool:
        return len(self.failed_critical) == 0


# ─── HTTP helper (stdlib only — no deps) ──────────────────


def http(
    method: str, url: str, body: dict | None = None, timeout: float = 20.0
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


def ok_code(code: int) -> bool:
    """POST endpoints return 201 Created — accept any 2xx."""
    return 200 <= code < 300


# ─── Verifier ─────────────────────────────────────────────


class Verifier:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.report = VerifyReport(base_url=base_url, started_at=datetime.now(UTC).isoformat())

    def check(
        self,
        name: str,
        group: str,
        fn: Callable[[], tuple[bool, str]],
        critical: bool = True,
    ) -> tuple[bool, str]:
        t0 = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"exception: {e}"
        dt = (time.perf_counter() - t0) * 1000
        self.report.checks.append(CheckResult(name, ok, detail, round(dt, 1), group, critical))
        icon = "✅" if ok else ("⚠️ " if not critical else "❌")
        print(f"  {icon} {name:42s} {detail}  ({dt:.0f}ms)")
        return ok, detail

    # ─── Groups ─────────────────────────────────────────

    def group_infrastructure(self) -> None:
        print("\n── Infrastructure ──")

        def health() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/health")
            if not ok_code(code):
                return False, f"HTTP {code}"
            ok = d.get("status") == "ok" and d.get("model_loaded") and d.get("database_connected")
            detail = f"status={d.get('status')} model={d.get('model_loaded')}"
            return ok, detail

        self.check("health", "infrastructure", health)

    def group_inference(self) -> None:
        print("\n── Inference ──")
        cases = [
            ("predict safe", "Hello, have a great stream!", "safe"),
            ("predict spam", "WIN FREE iPhone click here NOW!!!", "spam"),
            ("predict toxic", "you are stupid idiot, die", "toxic"),
        ]
        for name, text, expected in cases:

            def fn(text=text, expected=expected) -> tuple[bool, str]:
                code, d = http("POST", f"{self.base}/api/v1/predict", {"text": text})
                if not ok_code(code):
                    return False, f"HTTP {code}"
                detail = f"{d.get('label')} {d.get('confidence', 0):.2f}"
                return d.get("label") == expected, detail

            self.check(name, "inference", fn)

    def group_filter(self) -> None:
        print("\n── Filter API ──")

        def block() -> tuple[bool, str]:
            code, d = http(
                "POST",
                f"{self.base}/api/v1/filter",
                {
                    "text": "Get rich quick! Free money here!",
                    "rules": {
                        "block_labels": ["spam", "toxic"],
                        "flag_labels": [],
                        "threshold": 0.3,
                        "use_similarity_boost": True,
                    },
                    "source": "verify",
                },
            )
            if not ok_code(code):
                return False, f"HTTP {code}"
            return d.get("action") == "block", f"action={d.get('action')}"

        def allow() -> tuple[bool, str]:
            code, d = http(
                "POST", f"{self.base}/api/v1/filter", {"text": "hello world nice stream today"}
            )
            if not ok_code(code):
                return False, f"HTTP {code}"
            return d.get("action") == "allow", f"action={d.get('action')}"

        def stats() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/filter/stats")
            return ok_code(code), f"{d.get('total', '?')} events"

        self.check("filter blocks spam", "filter", block)
        self.check("filter allows safe", "filter", allow)
        self.check("filter stats", "filter", stats)

    def group_guardrails(self) -> None:
        print("\n── Guardrails ──")

        def spam() -> tuple[bool, str]:
            code, d = http(
                "POST",
                f"{self.base}/api/v1/guardrails/analyze",
                {"text": "WIN FREE iPhone! Click here NOW!!!"},
            )
            if not ok_code(code):
                return False, f"HTTP {code}"
            ok = d.get("action") in ("flag", "block")
            return ok, f"action={d.get('action')} score={d.get('final_score')}"

        def clean() -> tuple[bool, str]:
            code, d = http(
                "POST",
                f"{self.base}/api/v1/guardrails/analyze",
                {"text": "Hello, nice weather today"},
            )
            if not ok_code(code):
                return False, f"HTTP {code}"
            return d.get("action") == "allow", f"action={d.get('action')}"

        def layers() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/guardrails/layers")
            names = [x["name"] for x in d.get("layers", [])] if ok_code(code) else []
            return set(names) == {"regex", "lexicon", "ml", "embedding"}, f"{len(names)} layers"

        self.check("guardrails spam detected", "guardrails", spam)
        self.check("guardrails clean allowed", "guardrails", clean)
        self.check("guardrails 4 layers", "guardrails", layers)

    def group_data_loop(self) -> None:
        print("\n── Data & Feedback Loop ──")

        def add_and_stats() -> tuple[bool, str]:
            code, d = http(
                "POST",
                f"{self.base}/api/v1/dataset/add",
                {"text": "verify probe sample", "label": "safe"},
            )
            if not ok_code(code) or not d.get("success"):
                return False, f"HTTP {code}"
            total = d.get("total_samples", 0)
            return total > 0, f"total={total}"

        self.check("dataset add", "data", add_and_stats)

        def feedback() -> tuple[bool, str]:
            code, pred = http(
                "POST",
                f"{self.base}/api/v1/predict",
                {"text": "wonderful gameplay today"},
            )
            if not ok_code(code):
                return False, "predict failed"
            pid = pred.get("prediction_id")
            code2, fb = http(
                "POST",
                f"{self.base}/api/v1/feedback",
                {"prediction_id": pid, "feedback": "down"},
            )
            return ok_code(code2), f"feedback saved for {str(pid)[:8]}…"

        self.check("feedback loop", "data", feedback)

        def uncertain() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/active-learning/uncertain?limit=3")
            if not ok_code(code):
                return False, f"HTTP {code}"
            return isinstance(d.get("samples"), list), f"{len(d.get('samples', []))} samples"

        self.check("active learning queue", "data", uncertain, critical=False)

    def group_observability(self) -> None:
        print("\n── Observability & Analytics ──")

        def business() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/business/dashboard")
            keys = (
                "moderation_quality",
                "funnel",
                "label_distribution",
                "false_positive_cost",
            )
            ok = ok_code(code) and all(k in d for k in keys)
            return ok, "all metrics" if code == 200 else f"HTTP {code}"

        self.check("business dashboard", "observability", business)

        def drift() -> tuple[bool, str]:
            code, d = http("POST", f"{self.base}/api/v1/drift/analyze", {"window_hours": 24})
            if not ok_code(code):
                return False, f"HTTP {code}"
            return "overall_drift_score" in d, f"score={d.get('overall_drift_score')}"

        self.check("drift analysis", "observability", drift, critical=False)

        def alerts() -> tuple[bool, str]:
            code, d = http("GET", f"{self.base}/api/v1/alerts/thresholds")
            ok = ok_code(code) and "toxicity_rate" in d
            return ok, "thresholds ok" if code == 200 else f"HTTP {code}"

        self.check("alerting thresholds", "observability", alerts)

        def cost() -> tuple[bool, str]:
            code, _ = http("GET", f"{self.base}/api/v1/cost/summary")
            return ok_code(code), f"HTTP {code}"

        self.check("cost summary", "observability", cost, critical=False)

    def group_experiments(self) -> None:
        print("\n── Experiments ──")

        def lifecycle() -> tuple[bool, str]:
            code, exp = http(
                "POST",
                f"{self.base}/api/v1/experiments",
                {
                    "name": "verify-lifecycle",
                    "control_model": "mock-v0.1.0",
                    "treatment_model": "mock-v0.1.0",
                    "traffic_split": 0.5,
                },
            )
            if not ok_code(code) or "id" not in exp:
                return False, f"create HTTP {code}"
            eid = exp["id"]
            http("POST", f"{self.base}/api/v1/experiments/{eid}/start")
            http("GET", f"{self.base}/api/v1/experiments/{eid}/analyze")
            code3, _ = http("POST", f"{self.base}/api/v1/experiments/{eid}/stop")
            return ok_code(code3), "create→start→analyze→stop"

        self.check("experiment lifecycle", "experiments", lifecycle, critical=False)

    def group_streaming(self) -> None:
        print("\n── Streaming ──")

        def simulator() -> tuple[bool, str]:
            code, d = http("POST", f"{self.base}/api/v1/stream/simulator/start")
            started = d.get("status") in ("started", "already_running")
            time.sleep(2.5)
            http("POST", f"{self.base}/api/v1/stream/simulator/stop")
            return started and code == 200, f"started→stopped, status={d.get('status')}"

        self.check("simulator start/stop", "streaming", simulator, critical=False)

    def group_latency(self, skip_load: bool) -> None:
        print("\n── Latency burst (mini load) ──")
        if skip_load:
            print("  ⏭ skipped (--skip-load)")
            return

        def burst() -> tuple[bool, str]:
            latencies: list[float] = []
            fails = 0
            for i in range(30):
                code, d = http(
                    "POST",
                    f"{self.base}/api/v1/predict",
                    {"text": f"latency probe {i} nice game"},
                )
                if not ok_code(code):
                    fails += 1
                    continue
                latencies.append(d.get("processing_time_ms", 0))
            if not latencies:
                return False, "all requests failed"
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            ok = fails == 0 and p95 < 500
            return ok, f"30 reqs, {fails} fails, p50={p50:.0f}ms p95={p95:.0f}ms"

        self.check("30-request burst", "latency", burst, critical=False)

    # ─── Runner ─────────────────────────────────────────

    def run(self, skip_load: bool = False) -> int:
        print(f"🔍 NEXUS Verifier → {self.base}")
        print(f"   {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        self.group_infrastructure()
        self.group_inference()
        self.group_filter()
        self.group_guardrails()
        self.group_data_loop()
        self.group_observability()
        self.group_experiments()
        self.group_streaming()
        self.group_latency(skip_load)

        self.report.finished_at = datetime.now(UTC).isoformat()

        # Save JSON report
        reports_dir = Path(__file__).resolve().parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        out = reports_dir / f"verify_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(self._serialize(), indent=2, default=str))

        # Summary
        r = self.report
        print(f"\n{'═' * 60}")
        print(f"  {r.passed} passed / {r.failed} failed  →  report: {out}")
        if r.failed:
            print("\n  ⚠️  Failed checks:")
            for c in r.checks:
                if not c.ok:
                    tag = "CRITICAL" if c.critical else "non-critical"
                    print(f"    [{tag}] {c.group}/{c.name}: {c.detail}")
        print(f"{'═' * 60}")
        print(f"  System health: {'🟢 HEALTHY' if r.healthy else '🔴 DEGRADED'}")
        return 0 if r.healthy else 1

    def _serialize(self) -> dict:
        r = self.report
        return {
            "base_url": r.base_url,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "summary": {
                "total": len(r.checks),
                "passed": r.passed,
                "failed": r.failed,
                "healthy": r.healthy,
            },
            "checks": [
                {
                    "group": c.group,
                    "name": c.name,
                    "ok": c.ok,
                    "detail": c.detail,
                    "duration_ms": c.duration_ms,
                    "critical": c.critical,
                }
                for c in r.checks
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXUS autonomous verifier")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--skip-load", action="store_true")
    args = parser.parse_args()
    return Verifier(args.base_url).run(skip_load=args.skip_load)


if __name__ == "__main__":
    sys.exit(main())
