import logging

from redis import Redis
from rq import Queue
from rq.worker import SimpleWorker

import app.workers.tasks  # noqa: F401  (preloads the embedding model)
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)
    SimpleWorker([Queue("scoring", connection=conn)], connection=conn).work(with_scheduler=True)
