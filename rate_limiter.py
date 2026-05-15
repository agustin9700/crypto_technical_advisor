import threading
import time

import ccxt

import config


_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def is_enabled() -> bool:
    return bool(getattr(config, "GLOBAL_RATE_LIMIT_ENABLED", True))


def requests_per_second() -> float:
    value = getattr(config, "GLOBAL_RATE_LIMIT_REQUESTS_PER_SECOND", 3.0)
    try:
        return max(float(value), 0.1)
    except (TypeError, ValueError):
        return 3.0


def wait_for_slot() -> None:
    if not is_enabled():
        return

    global _LAST_REQUEST_AT
    min_interval = 1.0 / requests_per_second()
    with _LOCK:
        now = time.monotonic()
        wait_seconds = max(0.0, _LAST_REQUEST_AT + min_interval - now)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _LAST_REQUEST_AT = time.monotonic()


def call(func, *args, **kwargs):
    max_retries = max(int(getattr(config, "GLOBAL_RATE_LIMIT_MAX_RETRIES", 2)), 0)
    backoff = max(float(getattr(config, "GLOBAL_RATE_LIMIT_BACKOFF_SECONDS", 1.0)), 0.1)

    for attempt in range(max_retries + 1):
        wait_for_slot()
        try:
            return func(*args, **kwargs)
        except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as exc:
            if attempt >= max_retries:
                raise
            sleep_for = backoff * (2 ** attempt)
            print(f"WARNING: rate limit/backoff {sleep_for:.1f}s after {type(exc).__name__}: {exc}")
            time.sleep(sleep_for)
