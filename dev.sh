#!/usr/bin/env bash
cd ~/resume-matcher || exit 1
source venv/bin/activate
export PYTHONPATH=.
docker compose up -d db redis || { echo "Docker failed to start the database (see the error above)"; exit 1; }
for i in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' resume_matcher_db 2>/dev/null)" = "healthy" ] && break
  echo "Waiting for database..."; sleep 2
  if [ "$i" -eq 30 ]; then echo "Database did not become healthy"; exit 1; fi
done
uvicorn app.main:app --reload
