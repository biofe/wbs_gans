## WBS Coding School Project: Gans

Gans is a e-scooter company willing to expand to new cities. They want to focus
on city trip tourists, who come in by plane. Therefore, incoming flights at the
respective airports and the weather is interesting information that is pulled
via API and the geographic position is scraped from Wikipedia.

**Full write-up of the project and the VPS deployment:** [Gans, Grounded: What a Toy Data Pipeline Taught Me About Running Real Infrastructure](https://medium.com/@felix0180/gans-grounded-what-a-toy-data-pipeline-taught-me-about-running-real-infrastructure-be73255080c2)

### Pipeline

Three stages, the first feeding the other two:

1. **`scripts/fetch_cities.py`** — scrapes each city's Wikipedia page for its
   coordinates, country, and population. Run by hand whenever a new city is
   added; everything downstream picks it up automatically from there.
2. **`scripts/fetch_flights.py`** — uses those coordinates to find nearby
   airports via AeroDataBox, then pulls their scheduled arrivals.
3. **`scripts/fetch_weather.py`** — pulls a 3-hourly forecast per city from
   OpenWeatherMap.

The last two run on a schedule (see [`deploy/`](deploy/)); the first is a
one-off seed step.

### Schema

Defined in [`setup_schema.sql`](setup_schema.sql): `city`, `solar_time`,
`forecast`, and `arrival`, each with a disposable `_tmp` staging counterpart.
Every scheduled run writes to the `_tmp` table wholesale (safe, since nothing
queries it directly), then a stored procedure
(`update_city`/`update_solar_time`/`update_forecast`/`update_arrival`) merges
it into the permanent table via `INSERT ... ON DUPLICATE KEY UPDATE` — so the
tables anything else might be reading from are never dropped or left
momentarily empty.

### Deployment

Runs as two Docker containers on a VPS — MySQL (bound to loopback only, never
exposed publicly) and a Python container running the scheduled jobs via cron.
A sanitized copy of the actual Compose setup (secrets replaced with
placeholders) is in [`deploy/`](deploy/).

The full story — every obstacle hit setting this up and how each was fixed —
is written up in [`server/docker-mysql-setup.md`](server/docker-mysql-setup.md).
A matching [`server/teardown-checklist.md`](server/teardown-checklist.md)
documents how the project was later removed from the VPS without a trace. (The
project has since been torn down; the VPS itself and the SSH-hardening /
swap-file changes from that writeup were kept.)

### Tools

- Python:
  - Pandas
  - pymysql
  - requests
  - dotenv
  - BeautifulSoup
- [OpenWeather](https://openweathermap.org/)
- [AeroDataBox](https://rapidapi.com/aedbx-aedbx/api/aerodatabox)
- MySQL
- Docker / Podman
