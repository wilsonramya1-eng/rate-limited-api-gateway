from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def hit(client: httpx.AsyncClient, url: str) -> tuple[int, float]:
    start = time.perf_counter()
    response = await client.get(url)
    return response.status_code, (time.perf_counter() - start) * 1000


async def run(url: str, requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=20) as client:
        async def bounded():
            async with semaphore:
                return await hit(client, url)
        results = await asyncio.gather(*(bounded() for _ in range(requests)))
    statuses: dict[int, int] = {}
    for status, _ in results:
        statuses[status] = statuses.get(status, 0) + 1
    latencies = [latency for _, latency in results]
    print({"statuses": statuses, "p50_ms": round(statistics.median(latencies), 2), "max_ms": round(max(latencies), 2)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/gateway/get")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.requests, args.concurrency))

