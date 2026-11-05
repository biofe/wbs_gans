# VPS MySQL + Python Scheduler Setup — Build Log

Dockerized MySQL on a VPS (Debian 12), reachable remotely via
MySQL Workbench/CLI over an SSH tunnel, plus a Python container that runs scheduled
weather/flight-data fetch jobs via cron. An existing nginx-served website on the
host was never touched.

Project lives at `/opt/gans` on the server. Local notes/scripts live under
`06_gans/server` and `06_gans/scripts` respectively.

## Architecture

- MySQL is bound to `127.0.0.1:3306` on the VPS **only** — never reachable from the
  public internet. Remote admin access (Workbench/CLI) goes through an SSH tunnel.
- The Python jobs container talks to MySQL over a private Docker network
  (`gans-net`), by service name (`mysql`), completely separate from the
  loopback-bound host port above.
- Two MySQL accounts: `GANS_ADMIN_USER` (full rights on `gans`, for Workbench/CLI
  exploration) and `GANS_APP_USER` (least-privilege, for the Python jobs). Root is
  never used remotely.

## 1. Host hardening (permanent — intentionally *not* torn down later)

### 1.1 SSH: key-based login only, root login disabled

**Obstacle 1 — split-brain config.** `grep` showed both
`/etc/ssh/sshd_config` (`PasswordAuthentication no`) and
`/etc/ssh/sshd_config.d/50-cloud-init.conf` (`PasswordAuthentication yes`)
disagreeing. Debian's `sshd_config` has `Include /etc/ssh/sshd_config.d/*.conf` as
its first directive, and for sshd, **the first value encountered wins** — so the
cloud-init drop-in's `yes`, read first, silently overrode the main file's `no`.
Confirmed authoritatively with:
```bash
sudo sshd -T | grep -iE 'permitrootlogin|passwordauthentication'
```

**Obstacle 2 — root login still worked despite `PermitRootLogin no` on disk.**
`sshd -T` re-parses config files fresh from disk — it does *not* reflect what the
already-running sshd process loaded at its last start. The VPS had 396 days of
uptime with no reload, so the live process was still enforcing stale policy.

**Fix** — one drop-in file that wins the ordering conflict (sorts before
`50-cloud-init.conf`) and documents both overrides explicitly:
```bash
# /etc/ssh/sshd_config.d/10-harden.conf
PermitRootLogin no
PasswordAuthentication no
```
```bash
sudo systemctl reload ssh
```

**Prerequisite before disabling password auth**: install the existing (already
passphrase-protected) key pair's public half on the server first, and verify key
login works *in a second session* before closing the original one:
```bash
scp ~/.ssh/<key>.pub <user>@<host>:/tmp/laptop_key.pub
ssh <user>@<host> 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
  cat /tmp/laptop_key.pub >> ~/.ssh/authorized_keys && \
  chmod 600 ~/.ssh/authorized_keys && rm /tmp/laptop_key.pub'
ssh -i ~/.ssh/<key> <user>@<host>   # test in a NEW terminal, keep old one open
```

**Verified end state**: key login works; password login refused (no prompt at
all); `ssh root@host` refused; local `su -` to root from an already-authenticated
session still works (intentional recovery path, untouched).

*Note: a 30-character random password is not brute-forceable (~178 bits of
entropy) — the reason for key-based auth here is reduced exposure surface
(nothing transmitted/typed, no credential-stuffing bots succeed), not password
strength.*

### 1.2 Swap file

No swap existed on a 4 GB RAM box about to run MySQL + a Python container — added
as a safety net against OOM-kill, not for performance:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Project scaffold (`/opt/gans`)

```
/opt/gans/
├── docker-compose.yml
├── .env                      # secrets — chmod 600, never committed
├── mysql/
│   └── init/
│       └── 01-create-users.sh
└── python-jobs/
    ├── Dockerfile
    ├── entrypoint.sh
    ├── crontab
    ├── requirements.txt
    └── scripts/
        ├── fetch_weather.py
        ├── fetch_flights.py
        └── fetch_cities.py
```
```bash
sudo mkdir -p /opt/gans/mysql/init /opt/gans/python-jobs/scripts
sudo chown -R <user>:<user> /opt/gans
```

## 3. MySQL service

Bugs caught during drafting, each worth remembering:
- `image: myssql:8.4` → typo, should be `mysql:...`.
- `ports: "127.0.0.1:3306:3306"` with no leading `-` → invalid YAML for a list.
- Volume target `/var/vib/mysql` → should be `/var/lib/mysql` (MySQL's real data
  dir); as typo'd, the named volume silently wouldn't have persisted anything.
- Referencing `mysql-data`/`gans-net` inside the service without declaring them
  under top-level `volumes:`/`networks:` → Compose refuses to start
  ("refers to undefined volume/network").
- Forgot `MYSQL_DATABASE: gans` → schema never auto-created.

**Version mismatch**: started on `mysql:8.4`, but MySQL Workbench (tested against
the local `8.0.46` install) warned "only 8.0 is tested" and crashed on
"Connect anyway." Resolved by matching the local dev version exactly rather than
chasing the newer LTS line — `docker compose down -v` (safe, nothing of value in
an empty just-created schema yet) and switched to `mysql:8.0.46`.

**Memory discipline**: MySQL 8 auto-sizes its InnoDB buffer pool from *detected*
memory, which can be wrong inside a container. Capped explicitly instead of
trusting auto-detection:
```yaml
mem_limit: 1g
command: ["--innodb-buffer-pool-size=512M"]
```

Final `mysql` service:
```yaml
  mysql:
    image: mysql:8.0.46
    restart: "unless-stopped"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      GANS_ADMIN_USER: ${GANS_ADMIN_USER}
      GANS_ADMIN_PASSWORD: ${GANS_ADMIN_PASSWORD}
      GANS_APP_USER: ${GANS_APP_USER}
      GANS_APP_PASSWORD: ${GANS_APP_PASSWORD}
      MYSQL_DATABASE: gans
    ports:
      - "127.0.0.1:3306:3306"
    mem_limit: 1g
    command: ["--innodb-buffer-pool-size=512M"]
    volumes:
      - mysql-data:/var/lib/mysql
      - ./mysql/init:/docker-entrypoint-initdb.d:ro
    networks:
      - gans-net
```

## 4. MySQL users and schema

**Gotcha — host-based grants don't work the way you'd expect.** Connections
arriving through Docker's published-port NAT, or over the internal bridge network,
never actually appear to MySQL as coming from `localhost`/`127.0.0.1` — they arrive
from a bridge-gateway or container IP instead. Granting `@'localhost'` would
silently never match. Both accounts use `@'%'`; the real security boundary is
network isolation (loopback-only bind + SSH tunnel for the admin account,
no-published-port for the app account), not MySQL's host filter.

**Why `.sh` not `.sql`**: `/docker-entrypoint-initdb.d/*.sh` files run with bash and
can read environment variables for password substitution; `.sql` files are piped
in verbatim with no substitution — hardcoding real passwords in plain SQL would be
the alternative, and worse.

**`set -e` matters**: without it, a failed `CREATE USER`/`GRANT` statement inside
the heredoc wouldn't necessarily stop the script or fail the container's init step
loudly — you could end up with a container that looks healthy but is missing an
account.

`mysql/init/01-create-users.sh`:
```bash
#!/bin/bash
set -e

mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
  CREATE USER '${GANS_ADMIN_USER}'@'%' IDENTIFIED BY '${GANS_ADMIN_PASSWORD}';
  GRANT ALL PRIVILEGES ON gans.* TO '${GANS_ADMIN_USER}'@'%';

  CREATE USER '${GANS_APP_USER}'@'%' IDENTIFIED BY '${GANS_APP_PASSWORD}';
  GRANT SELECT, INSERT, UPDATE, EXECUTE, CREATE, DROP ON gans.* TO '${GANS_APP_USER}'@'%';
EOSQL
```
App-user privilege reasoning, from what the Python scripts actually do:
`SELECT` (`pandas.read_sql`), `INSERT`/`CREATE` (`pandas.to_sql`, which creates the
table if missing), `DROP` (because `to_sql(..., if_exists='replace')` is used for
staging tables), `EXECUTE` (`pymysql` `cursor.callproc()` for the update stored
procedures).

*(`FLUSH PRIVILEGES` is unnecessary here — it only matters after directly editing
the grant tables; `CREATE USER`/`GRANT` apply immediately on their own.)*

**Init scripts only run once**, against an empty data directory on first boot — so
user creation had to be written and in place *before* the very first
`docker compose up`, or we'd have had to wipe the volume to re-trigger it.

**Loading the actual schema** (a pre-existing local `setup_schema.sql` with
`DROP DATABASE IF EXISTS gans; CREATE DATABASE gans; ...`): safe to keep the
drop/recreate — MySQL's database-level `GRANT ... ON gans.*` entries are matched
by schema *name*, not tied to the physical object, so they survive a drop+recreate
of the same-named schema. No need to upload the file to the server at all — the
`mysql` client reads it from the local filesystem and streams the statements over
the already-open tunneled connection:
```bash
mysql -h 127.0.0.1 -P 3307 -u <GANS_ADMIN_USER> -p gans < setup_schema.sql
```

## 5. Remote access

**SSH tunnel** (manual, held open in its own terminal):
```bash
ssh -i ~/.ssh/<key> -N -L 3307:127.0.0.1:3306 <user>@<host>
```

**MySQL Workbench — two separate failures encountered:**
1. *"Standard TCP/IP over SSH" connection method*: `Access denied for 'none'.
   Authentication that can continue: publickey` — Workbench bundles its own old
   `libssh2`-based SSH client, which frequently can't parse modern key formats
   (`ed25519`, or RSA in the newer OpenSSH container format rather than legacy
   PEM). Worked around by holding the tunnel externally (above) and pointing
   Workbench at plain `Standard TCP/IP`, host `127.0.0.1`, port `3307` instead —
   sidesteps Workbench's SSH implementation entirely.
2. *Version-compatibility crash*: "only 8.0 is properly tested," crashed on
   "Connect anyway" — resolved by matching server version to `8.0.46` (section 3).
3. *Still crashes opening the connection on NixOS specifically* — log showed
   `Module WbAdmin not found` / `OS not found on supported OS list`. NixOS's
   non-FHS layout breaks Workbench's native plugin loading (the piece that loads
   the schema tree / server-status view). **Unresolved, deferred.** Options for
   later: `steam-run mysql-workbench` (FHS wrapper), switch to DBeaver (handles
   NixOS cleanly, no native plugin-loading issue), or run the official Oracle
   tarball via `nix-ld`.

**Working fallback — CLI via the same tunnel.** NixOS's current nixpkgs only ships
`mysql84`'s client, not `8.0.46` — used anyway, since the wire protocol doesn't
require client/server version parity (only Workbench's own tooling had actual
version gating):
```bash
nix-shell -p mysql84 --run 'mysql -h 127.0.0.1 -P 3307 -u <user> -p gans'
```
First attempt at this failed with `ERROR 2003 ... (111)` — turned out to be run
via `podman compose exec` inside an unrelated *local* container (wrong working
directory), and even conceptually wrong regardless: a container has its own
network namespace, so `127.0.0.1` inside any container never refers to the host's
loopback where the tunnel's listening socket actually lives. Fixed by running the
client as a plain process on the laptop host instead.

## 6. Python scheduler container

**`requirements.txt` gap**: all three scripts `import requests`, but it was
missing from the file (sqlalchemy — needed implicitly by `pandas.read_sql`/`to_sql`
when passed a connection-string URL — was correctly included).

**Env var naming trap (in the scripts, not a bug to fix, just to know)**: the
scripts read `os.environ["MYSQL_ROOT_PASSWORD"]` as "whatever password belongs to
`MYSQL_USER`" — on the VPS this is deliberately set to `GANS_APP_PASSWORD`, never
the real root password. `MYSQL_HOST`/`MYSQL_PORT` change from the tunnel values
(`127.0.0.1`/`3307`, used for local testing) to the internal Docker values
(`mysql`/`3306`) once running alongside the `mysql` service on `gans-net`.

**Cron does not inherit container environment variables** — it spawns jobs with
its own minimal environment. Fixed by dumping the live environment into
`/etc/environment` at container start, which Debian's cron (via PAM) applies to
every job it runs:
```bash
# entrypoint.sh
#!/bin/bash
printenv | grep -v "no_proxy" >> /etc/environment
cron
tail -F /var/log/cron.log
```

**Dockerfile bug caught and removed**: `crontab /etc/cron.d/gans-cron` was
redundant and wrong — `/etc/cron.d/*` files are picked up automatically; running
`crontab` on top tried to install the *same* file as root's personal crontab,
whose format has no user column, so it misparsed `root` as the start of the
command. Harmless (the real `/etc/cron.d` jobs still ran fine) but pointless and
confusing — removed.

**Observability gap**: job output was redirected to a file
(`>> /var/log/cron.log`) inside the container, invisible to `docker compose logs`
by design. Fixed by backgrounding `cron` and making `tail -F /var/log/cron.log`
the foreground process instead, so output streams into Docker's log capture going
forward.

**Verifying it's actually working** (rather than waiting hours for the real
schedule):
```bash
docker compose exec python-jobs ps aux                      # cron + tail both running?
docker compose exec python-jobs cat /etc/cron.d/gans-cron    # schedule loaded correctly?
docker compose exec python-jobs python /app/scripts/fetch_weather.py   # full pipeline, right now
docker compose exec python-jobs sh -c 'echo test >> /var/log/cron.log' # isolate the log-streaming pipe
docker compose logs --tail 5 python-jobs
```

`python-jobs/Dockerfile`:
```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/fetch_weather.py scripts/fetch_flights.py scripts/fetch_cities.py ./scripts/
COPY crontab /etc/cron.d/gans-cron
RUN chmod 0644 /etc/cron.d/gans-cron && touch /var/log/cron.log

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```
*(deliberately names the three `.py` files individually rather than
`COPY scripts/ ./scripts/`, so the local `scripts/.env` with real secrets can
never end up baked into an image layer.)*

`python-jobs/crontab` (note: required user field, explicit `PATH` since cron's
default is minimal, and a mandatory trailing blank line or the last entry is
silently ignored):
```
PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/bin

0 */3 * * * root /usr/local/bin/python /app/scripts/fetch_weather.py >> /var/log/cron.log 2>&1
0 5 * * * root /usr/local/bin/python /app/scripts/fetch_flights.py >> /var/log/cron.log 2>&1

```
`fetch_cities.py` is copied into the image but intentionally **not** scheduled —
it's a one-off Wikipedia-scraping seed script, run manually via
`docker compose exec python-jobs python scripts/fetch_cities.py` whenever a new
city is added.

Final `python-jobs` compose service:
```yaml
  python-jobs:
    build: ./python-jobs
    restart: unless-stopped
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_USER: ${GANS_APP_USER}
      MYSQL_ROOT_PASSWORD: ${GANS_APP_PASSWORD}
      API_KEY_OPENWEATHER: ${API_KEY_OPENWEATHER}
      API_KEY_OPENAEROBOX: ${API_KEY_OPENAEROBOX}
    depends_on:
      - mysql
    networks:
      - gans-net
```

## Open items

- MySQL Workbench's GUI still doesn't run on NixOS (section 5, point 3) —
  CLI access works fully in the meantime.
- A teardown/cleanup checklist for `/opt/gans` (what to remove to leave zero trace,
  explicitly excluding the permanent SSH-hardening and swap-file changes from
  section 1) has not been written yet — separate follow-up.
