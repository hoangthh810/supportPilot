#!/bin/sh
set -eu

/bin/sh /db/run-bootstrap.sh

psql \
  --no-psqlrc \
  --quiet \
  --set ON_ERROR_STOP=1 \
  --dbname "$POSTGRES_BOOTSTRAP_DATABASE_URL" \
  --file /db/phase1-extensions.sql
