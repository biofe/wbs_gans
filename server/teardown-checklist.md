# Teardown / Cleanup Checklist — `/opt/gans`

Scope: everything created for the MySQL + Python-scheduler project. Following
this fully removes every trace of the project from the VPS, with **zero impact**
on the existing nginx-served website or anything else already running on the box.

## What this does *not* touch

Two changes made along the way are permanent, deliberate improvements to the host
— not part of this project's footprint, and **not** reverted by this checklist:

- **SSH hardening** (`/etc/ssh/sshd_config.d/10-harden.conf`: key-only login, no
  root over SSH) — decided to keep.
- **The 2 GB swap file** (`/swapfile` + its `/etc/fstab` entry) — decided to keep.

If you ever do want those gone too, that's a separate, explicit decision — don't
fold it into "cleaning up the gans project."

## Before you start: back up any data you want to keep

Removing the project includes deleting the `mysql-data` volume, which erases the
database entirely — including every weather/flight row the Python jobs have
collected so far. If you want to keep any of it, dump it first:
```bash
docker compose -f /opt/gans/docker-compose.yml exec mysql \
  bash -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" gans' > ~/gans-backup.sql
```
Copy `~/gans-backup.sql` off the server (`scp`) before continuing if you want it
preserved anywhere. Skip this entirely if you don't care about the collected data.

## 1. Stop and remove all Docker objects

One command handles containers, the custom network, the named volume, and both
images (the pulled `mysql:8.0.46` and the custom-built `python-jobs` image) in one
shot:
```bash
cd /opt/gans
docker compose down --rmi all -v --remove-orphans
```
- `--rmi all` — removes every image used by the compose file (not just the
  containers), so nothing lingers in `docker images`.
- `-v` — removes the `mysql-data` named volume. **This is the destructive step**
  covered by the backup note above.
- `--remove-orphans` — cleans up any leftover containers from earlier
  experiments (e.g. if an old `mysql:8.4` container from before the version
  switch is still hanging around under a different name).

## 2. Remove the project directory on the server

This deletes the compose file, the `.env` (plaintext secrets — API keys, DB
passwords), the init script, the Dockerfile, crontab, and the copied Python
scripts:
```bash
sudo rm -rf /opt/gans
```
There's no backup of this directory elsewhere on the server, so once it's gone,
any secrets that lived only in that `.env` are gone for good (your local copy at
`06_gans/scripts/.env` is unaffected — this only removes the server's copy).

## 3. Verify nothing was left behind

```bash
docker ps -a                 # only deploy-upload-1 (and anything else pre-existing) should remain
docker network ls            # gans-net gone; bridge/deploy_default/host/none untouched
docker volume ls             # mysql-data gone
docker images                # mysql:8.0.46 and the python-jobs image gone
ls /opt                      # gans/ gone
ss -tulpn | grep 3306        # nothing listening — MySQL fully stopped
```
And confirm the existing site is untouched:
```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'   # deploy-upload-1 still there, unchanged
curl -I https://<your-site-domain>                                # still responding normally
```

## 4. Laptop-side loose ends (optional, cosmetic)

- **Close the SSH tunnel** if it's still running in a terminal somewhere:
  ```bash
  pgrep -af 'ssh.*3307:127.0.0.1:3306'   # find it
  kill <pid>                              # or just close that terminal window
  ```
- **Remove the MySQL Workbench connection profiles** created for this project
  (both the abandoned "Standard TCP/IP over SSH" one and the working
  "Standard TCP/IP" one pointed at `127.0.0.1:3307`) via Workbench's connection
  manager — only if you don't want dead entries pointing at a now-gone endpoint.

- **Not removed, deliberately**: your local notes and scripts under
  `06_gans/server/` and `06_gans/scripts/` (including this checklist and the
  build log) — these are your own learning record, not server-side trace, and
  stay regardless of whether you tear the VPS side down.

## Summary

| Item | Action |
|---|---|
| `mysql` + `python-jobs` containers, `gans-net`, `mysql-data` volume, both images | removed by `docker compose down --rmi all -v --remove-orphans` |
| `/opt/gans` directory (compose file, `.env`, scripts, Dockerfile) | removed by `sudo rm -rf /opt/gans` |
| SSH hardening (`10-harden.conf`) | **kept** — permanent, out of scope |
| Swap file (`/swapfile`, `/etc/fstab` entry) | **kept** — permanent, out of scope |
| Existing nginx-served site / `deploy-upload-1` | untouched throughout |
| Local `06_gans/` notes and scripts | untouched — yours to keep |
