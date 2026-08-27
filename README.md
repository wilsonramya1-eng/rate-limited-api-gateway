# Rate-Limited API Gateway

A lightweight FastAPI reverse proxy that protects upstream services from traffic bursts and abuse. It includes exact sliding-window and token-bucket algorithms, per-client isolation, standard rate-limit headers, a health endpoint, Docker packaging, and a concurrent load-test utility.

## Real-world scenario

An internal API becomes unstable during traffic spikes. Rather than add rate limiting separately to every service, this gateway applies a reusable policy at the edge and returns `429` responses with a useful `Retry-After` header.

## Run

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e ".[dev]"
uvicorn gateway.app:app --reload
```

Try `http://localhost:8000/gateway/get`, then simulate a burst:

```bash
python load_test.py --requests 100 --concurrency 20
pytest
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `UPSTREAM_URL` | `https://httpbin.org` | Backend service |
| `RATE_LIMIT_ALGORITHM` | `token_bucket` | `token_bucket` or `sliding_window` |
| `RATE_LIMIT` | `60` | Requests or bucket capacity |
| `RATE_WINDOW_SECONDS` | `60` | Window/refill duration |

For multi-instance production deployment, replace the in-process event/token store with Redis and make trusted-proxy handling explicit.

## Architecture

`Client -> client identity -> limiter -> proxy -> upstream service`

The implementation deliberately separates rate-limiting algorithms from HTTP proxy behavior, making it easy to test policies independently or add a distributed store.
