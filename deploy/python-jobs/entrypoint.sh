#!/bin/bash
# cron spawns jobs with its own minimal environment and does not inherit
# whatever Docker injected into this container. Debian's cron reads
# /etc/environment (via PAM) and applies it to every job it runs, so we dump
# the live environment there before starting cron.
printenv | grep -v "no_proxy" >> /etc/environment

# Backgrounded so `tail -F` below can be the foreground process instead —
# that way job output (redirected to /var/log/cron.log by the crontab)
# streams into `docker logs` rather than disappearing into a file no one
# is watching.
cron
tail -F /var/log/cron.log
