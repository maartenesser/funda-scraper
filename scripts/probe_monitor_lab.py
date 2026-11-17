"""Probe only the owned synthetic Worker; never makes a Funda request."""

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from funda_scraper.monitor_lab import HTTPSource, LabConfig, Monitor


def probe(origin, allow_local=False):
    config = LabConfig(origin, allow_local=allow_local)
    source = HTTPSource(config)
    checks = []
    now = datetime.now(timezone.utc)
    try:
        with tempfile.TemporaryDirectory(prefix="funda-synthetic-") as temp:
            with Monitor(Path(temp) / "incremental.sqlite", config, source) as monitor:
                baseline = monitor.run(now, "initial")
                new = monitor.run(now, "new")
                changed = monitor.run(now, "changed")
                checks.append(
                    {
                        "case": "baseline",
                        "passed": baseline["status"] == "COMPLETE"
                        and baseline["baseline_items"] == 1,
                        "result": baseline,
                    }
                )
                checks.append(
                    {
                        "case": "new_and_duplicate",
                        "passed": new["status"] == "COMPLETE"
                        and new["new_items"] == 1
                        and new["details_fetched"] == 1
                        and new["valid_records"] == 1
                        and new["deferred"] == 0,
                        "result": new,
                    }
                )
                checks.append(
                    {
                        "case": "changed",
                        "passed": changed["status"] == "COMPLETE"
                        and changed["changed_items"] == 1
                        and changed["valid_records"] == 1
                        and changed["deferred"] == 0,
                        "result": changed,
                    }
                )
            for scenario, expected in [
                ("blocked", "BLOCKED"),
                ("rate", "BLOCKED"),
                ("captcha", "BLOCKED"),
                ("unknown", "FAILED"),
                ("redirect", "FAILED"),
                ("empty", "COMPLETE"),
            ]:
                with Monitor(Path(temp) / (scenario + ".sqlite"), config, source) as monitor:
                    result = monitor.run(now, scenario)
                    passed = result["status"] == expected
                    if scenario == "unknown":
                        passed = passed and result.get("reason") == "UNRECOGNIZED_PAGE"
                    if scenario == "redirect":
                        passed = passed and result.get("reason") == "HTTP_NOT_OK"
                    if expected == "BLOCKED":
                        passed = passed and monitor.run(now, "initial")["status"] == "PAUSED"
                    checks.append({"case": scenario, "passed": passed, "result": result})
    finally:
        source.close()
    return {
        "status": "PASS" if all(c["passed"] for c in checks) else "FAIL",
        "generated_at": now.isoformat(),
        "mode": "synthetic",
        "funda_enabled": False,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--allow-local", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe(args.origin, args.allow_local)
    value = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(value + "\n")
    print(value)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
