#!/bin/bash
# Runs once, automatically, the first time the mysql container starts against
# an empty data directory (see /docker-entrypoint-initdb.d in the official
# MySQL image docs). set -e so a failed statement aborts loudly instead of
# leaving a container that looks healthy but is missing an account.
set -e

# Both accounts use host '%' rather than 'localhost': connections arriving
# through Docker's bridge network never actually look like localhost to
# MySQL, so a 'localhost'-scoped grant would silently never match. The real
# security boundary here is network isolation (see docker-compose.yml), not
# MySQL's host matching.
mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
  CREATE USER '${GANS_ADMIN_USER}'@'%' IDENTIFIED BY '${GANS_ADMIN_PASSWORD}';
  GRANT ALL PRIVILEGES ON gans.* TO '${GANS_ADMIN_USER}'@'%';

  CREATE USER '${GANS_APP_USER}'@'%' IDENTIFIED BY '${GANS_APP_PASSWORD}';
  GRANT SELECT, INSERT, UPDATE, EXECUTE, CREATE, DROP ON gans.* TO '${GANS_APP_USER}'@'%';
EOSQL
