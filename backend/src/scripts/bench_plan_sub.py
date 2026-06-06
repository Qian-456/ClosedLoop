import argparse
import json
import os
import random
import sys
import time
from typing import Any

import httpx

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from closedloop.core.config import get_config
from closedloop.core.logger import LoggerManager, logger
from closedloop.utils.benchmarks import build_default_constraints_cases, summarize_latencies


def _load_cases(path: str | None) -> list[dict[str, Any]]:
    """Load benchmark constraints cases from a JSON file, or fallback to built-in defaults."""
    if not path:
        return build_default_constraints_cases()

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list) or not payload:
        raise ValueError("cases file must be a non-empty JSON list")
    cases: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cases.append(item)
    if not cases:
        raise ValueError("cases file contains no valid dict cases")
    return cases


def _dump_json(path: str, payload: dict[str, Any]) -> None:
    """Write benchmark results into a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> int:
    """Run plan_sub_backend (/plan) benchmark and print latency percentiles."""
    parser = argparse.ArgumentParser(description="Benchmark plan_sub_backend /plan latency (P50/P99).")
    parser.add_argument("--url", default="http://127.0.0.1:8001/plan", help="Plan sub service URL for /plan.")
    parser.add_argument("--runs", type=int, default=1000, help="Total request runs to measure.")
    parser.add_argument("--cases", type=int, default=20, help="How many cases to take from the cases list.")
    parser.add_argument("--cases-file", default=None, help="Optional JSON list file containing constraints dicts.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for case order shuffling.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle request order to reduce warm/cold bias.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds per request.")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup request count (not measured).")
    parser.add_argument(
        "--out",
        default="backend/src/logs/bench_plan_sub_results.json",
        help="Output JSON file path for benchmark summary.",
    )
    args = parser.parse_args()

    config = get_config()
    LoggerManager.setup(config)

    cases_all = _load_cases(args.cases_file)
    cases = cases_all[: max(1, min(args.cases, len(cases_all)))]
    if not cases:
        raise ValueError("no cases available")

    runs = int(args.runs)
    if runs <= 0:
        raise ValueError("runs must be > 0")

    random.seed(int(args.seed))
    case_indexes = [i % len(cases) for i in range(runs)]
    if args.shuffle:
        random.shuffle(case_indexes)

    logger.info(
        "phase=bench_plan_sub | msg=benchmark_start "
        f"| url={args.url} | runs={runs} | cases={len(cases)} | timeout={args.timeout}s"
    )

    with httpx.Client(timeout=float(args.timeout), trust_env=False, proxy=None) as client:
        for i in range(int(args.warmup)):
            case_idx = i % len(cases)
            payload = {"constraints": cases[case_idx], "top_k": 1, "session_id": f"bench_warmup_{case_idx}"}
            try:
                client.post(args.url, json=payload).raise_for_status()
            except Exception:
                continue

        latencies_ms: list[float] = []
        success_count = 0
        error_count = 0

        for run_index, case_idx in enumerate(case_indexes, start=1):
            payload = {"constraints": cases[case_idx], "top_k": 1, "session_id": f"bench_case_{case_idx}"}
            started_at = time.perf_counter()
            try:
                resp = client.post(args.url, json=payload)
                resp.raise_for_status()
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"phase=bench_plan_sub | msg=request_failed | run={run_index} | error={e}")
            finally:
                elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                latencies_ms.append(float(elapsed_ms))

        summary = summarize_latencies(latencies_ms, success_count=success_count, error_count=error_count)
        output = {
            "meta": {
                "url": args.url,
                "runs": runs,
                "cases": len(cases),
                "seed": int(args.seed),
                "shuffle": bool(args.shuffle),
                "timeout": float(args.timeout),
                "warmup": int(args.warmup),
            },
            "summary": summary.to_dict(),
        }

        _dump_json(args.out, output)

        logger.info(
            "phase=bench_plan_sub | msg=benchmark_done "
            f"| success={success_count} | error={error_count} "
            f"| p50_ms={summary.p50_ms:.1f} | p99_ms={summary.p99_ms:.1f} | mean_ms={summary.mean_ms:.1f} "
            f"| out={args.out}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

