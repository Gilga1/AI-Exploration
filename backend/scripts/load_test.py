"""Load /agent/invoke and confirm eval overhead stays off the response path.

Usage: python -m scripts.load_test --concurrency 8 --requests 40
Reports p50/p95 latency of the live response; the DoD is that adding the async
eval pipeline does not materially change these numbers (compare with
EVAL_SAMPLING_RATE=0 vs 1).
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

QUESTIONS = [
    "What does Acme Orbit sell?",
    "calculate 12*12",
    "How does OrbitNote sync handwritten notes?",
    "Which file formats can OrbitNote export?",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--requests", type=int, default=40)
    args = parser.parse_args()

    latencies: list[float] = []
    errors = 0

    def one_call(index: int) -> None:
        nonlocal errors
        question = QUESTIONS[index % len(QUESTIONS)]
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{args.base_url}/api/v1/agent/invoke",
                    json={"question": question},
                )
                response.raise_for_status()
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - start) * 1000)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(one_call, range(args.requests)))

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"requests={args.requests} concurrency={args.concurrency} errors={errors}")
    print(f"p50={p50:.1f}ms  p95={p95:.1f}ms  max={latencies[-1]:.1f}ms")
    print("(eval scoring is asynchronous; compare p50/p95 across sampling rates)")


if __name__ == "__main__":
    main()
