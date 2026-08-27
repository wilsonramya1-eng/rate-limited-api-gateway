from gateway.limiter import SlidingWindow, TokenBucket, client_key


def test_token_bucket_refills_over_time():
    limiter = TokenBucket(2, 1)
    assert limiter.check("a", now=0).allowed
    assert limiter.check("a", now=0).allowed
    blocked = limiter.check("a", now=0)
    assert not blocked.allowed and blocked.retry_after == 1
    assert limiter.check("a", now=1).allowed


def test_sliding_window_expires_old_events():
    limiter = SlidingWindow(2, 10)
    assert limiter.check("a", now=0).allowed
    assert limiter.check("a", now=1).allowed
    assert not limiter.check("a", now=2).allowed
    assert limiter.check("a", now=10.1).allowed


def test_clients_are_isolated_and_api_key_wins():
    limiter = TokenBucket(1, 1)
    assert limiter.check("a", now=0).allowed
    assert limiter.check("b", now=0).allowed
    assert client_key({"x-api-key": "customer"}, "127.0.0.1") == "api:customer"

