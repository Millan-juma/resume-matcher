import logging

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry

from app.core.config import settings
from app.workers.tasks import score_application

log = logging.getLogger(__name__)

# Short timeouts so the API never hangs on a dead Redis
_redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=2)
queue = Queue("scoring", connection=_redis)


def enqueue_scoring(application_id: str) -> bool:
    try:
        queue.enqueue(
            "app.workers.tasks.score_job", application_id,
            job_timeout=300,
            retry=Retry(max=3, interval=[10, 30, 90]),
            result_ttl=0,         # nothing to keep: the result lives in the database
            failure_ttl=86400,    # keep failed jobs 24h for inspection
        )
        return True
    except RedisError:
        log.exception("Could not enqueue scoring job")
        return False


def dispatch_scoring(background, application_id: str) -> None:
    """Use the Redis queue; fall back to an in-process task if it is unavailable."""
    if settings.queue_mode == "redis" and enqueue_scoring(application_id):
        return
    background.add_task(score_application, application_id)
