# Deployment

This is a sanitized copy of the Docker Compose setup actually running the
`gans` pipeline on a VPS: a loopback-bound MySQL container plus a Python
container that runs the two scheduled scripts (`fetch_weather.py` every 3
hours, `fetch_flights.py` daily) via cron. Real secrets have been replaced
with `${VAR}` placeholders throughout — see `.env.example`.

For the reasoning behind these specific choices (why MySQL is never exposed
publicly, why there are two separate least-privilege MySQL accounts instead
of one, the cron/Docker gotchas, etc.), see the write-up linked from the
[main README](../README.md).

## Bringing it up

```bash
cp .env.example .env        # fill in real values — never commit this file
docker compose up -d --build
```

The schema itself (`city`, `solar_time`, `forecast`, `arrival`, their staging
tables, and the merge stored procedures) is **not** created automatically by
this compose file — it's defined in [`setup_schema.sql`](../setup_schema.sql)
at the repo root and needs to be applied once, separately, e.g.:

```bash
mysql -h 127.0.0.1 -P 3306 -u <GANS_ADMIN_USER> -p < ../setup_schema.sql
```

(`fetch_cities.py` is included in the image but intentionally **not**
scheduled — it's a one-off seed script for adding a new city, run by hand
with `docker compose exec python-jobs python scripts/fetch_cities.py`.)
