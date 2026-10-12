from functools import wraps
import asyncio

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.rediss import redis_client


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

            current_requests = redis_client.get(redis_key) 

            if current_requests is None:
                redis_client.set(redis_key, 1, ex=time_window)

            elif int(current_requests) < max_requests:
                redis_client.incr(redis_key)

            else:
                retry_after = redis_client.ttl(redis_key)

                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds."
                )

            if is_coroutine:
                return await func(*args, **kwargs)
            else:
                return await run_in_threadpool(func, *args, **kwargs)

        return wrapper

    return decorator