from __future__ import annotations

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .limiter import SlidingWindow, TokenBucket, client_key


ALGORITHM = os.getenv("RATE_LIMIT_ALGORITHM", "token_bucket")
LIMIT = int(os.getenv("RATE_LIMIT", "60"))
WINDOW_SECONDS = float(os.getenv("RATE_WINDOW_SECONDS", "60"))
UPSTREAM = os.getenv("UPSTREAM_URL", "https://httpbin.org")


def build_limiter():
    if ALGORITHM == "sliding_window":
        return SlidingWindow(LIMIT, WINDOW_SECONDS)
    return TokenBucket(LIMIT, LIMIT / WINDOW_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(base_url=UPSTREAM, timeout=10.0)
    app.state.limiter = build_limiter()
    yield
    await app.state.http.aclose()


app = FastAPI(title="Rate-Limited API Gateway", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "algorithm": ALGORITHM}


@app.api_route("/gateway/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    key = client_key(dict(request.headers), request.client.host if request.client else None)
    decision = request.app.state.limiter.check(key)
    rate_headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if not decision.allowed:
        rate_headers["Retry-After"] = str(max(1, round(decision.retry_after)))
        return JSONResponse({"error": "rate_limit_exceeded"}, status_code=429, headers=rate_headers)

    excluded = {"host", "content-length", "connection"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in excluded}
    upstream = await request.app.state.http.request(
        request.method,
        f"/{path}",
        params=request.query_params,
        content=await request.body(),
        headers=headers,
    )
    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}}
    response_headers.update(rate_headers)
    return Response(upstream.content, status_code=upstream.status_code, headers=response_headers, media_type=upstream.headers.get("content-type"))

