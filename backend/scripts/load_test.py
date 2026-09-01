"""Load /agent/invoke and confirm eval overhead stays off the response path."""

from __future__ import annotations

import argparse
import statistics
import threading
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
    parser.add_argument("--api-key", default=None, help="Value for the X-API-Key header")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--requests", type=int, default=40)
    args = parser.parse_args()

    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    latencies: list[float] = []
    error_count = 0
    error_lock = threading.Lock()

    def one_call(index: int) -> None:
        nonlocal error_count
        question = QUESTIONS[index % len(QUESTIONS)]
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=30.0, headers=headers) as client:
                response = client.post(
                    f"{args.base_url}/api/v1/agent/invoke",
                    json={"question": question},
                )
                response.raise_for_status()
        except Exception:
            with error_lock:
                error_count += 1
        else:
            latencies.append((time.perf_counter() - start) * 1000)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(one_call, range(args.requests)))

    if not latencies:
        print(f"requests={args.requests} concurrency={args.concurrency} errors={error_count}")
        print("No successful requests recorded.")
        raise SystemExit(1)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"requests={args.requests} concurrency={args.concurrency} errors={error_count}")
    print(f"successful={len(latencies)} p50={p50:.1f}ms  p95={p95:.1f}ms  max={latencies[-1]:.1f}ms")
    print("(eval scoring is asynchronous; compare p50/p95 across sampling rates)")
    if error_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
