from functools import wraps
import asyncio
import logging

import redis
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.rediss import redis_client

logger = logging.getLogger(__name__)


def rate_limit(max_requests: int, time_window: int):
    def decorator(func):
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):

            request: Request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise RuntimeError(
                    "Request object not found. Add 'request: Request' to your route."
                )

            client_ip = request.client.host if request.client else "unknown" #request.client returns a object ,address(host,port)
            endpoint = request.url.path

            redis_key = f"rate_limit:{client_ip}:{endpoint}"

            try:
                # INCR is atomic, so concurrent requests can't slip past the limit.
                # The expiry is only set on the first hit of each window.
                current_requests = redis_client.incr(redis_key)
                if current_requests == 1:
                    redis_client.expire(redis_key, time_window)
                retry_after = None
                if current_requests > max_requests:
                    retry_after = redis_client.ttl(redis_key)
                    if retry_after < 0:
                        # Key lost its expiry (e.g. crash between INCR and EXPIRE); repair it
                        redis_client.expire(redis_key, time_window)
                        retry_after = time_window
            except redis.RedisError:
                # Fail open: a Redis outage shouldn't take the whole API down
                logger.warning("Rate limiter unavailable, allowing request", exc_info=True)
                current_requests, retry_after = 0, None

            if current_requests > max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

            if is_coroutine:
                return await func(*args, **kwargs)
            else:
                return await run_in_threadpool(func, *args, **kwargs)

        return wrapper

    return decorator
