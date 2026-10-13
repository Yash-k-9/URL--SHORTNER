import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from core.config import REDIS_HOST, REDIS_PORT

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    # Fail fast so callers can fall back to Postgres instead of hanging.
    # redis-py retries with exponential backoff by default (~25s when Redis is down).
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
    retry=Retry(NoBackoff(), 0),
)
