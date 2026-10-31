# Built with context = repo root (see ../docker-compose.yml), so paths below
# are relative to the repository, not this directory.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY scripts/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copied individually rather than the whole scripts/ directory, so a local
# scripts/.env with real secrets can never end up baked into an image layer.
COPY scripts/fetch_weather.py scripts/fetch_flights.py scripts/fetch_cities.py ./scripts/

COPY deploy/python-jobs/crontab /etc/cron.d/gans-cron
RUN chmod 0644 /etc/cron.d/gans-cron && touch /var/log/cron.log

COPY deploy/python-jobs/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
