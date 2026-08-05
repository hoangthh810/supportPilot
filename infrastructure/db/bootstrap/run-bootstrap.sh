#!/bin/sh
set -eu

require_environment() {
  variable_name="$1"
  eval "variable_value=\${${variable_name}:-}"
  if [ -z "$variable_value" ]; then
    echo "Required DB-000 environment variable is missing: $variable_name" >&2
    exit 64
  fi
}

for variable_name in \
  POSTGRES_BOOTSTRAP_DATABASE_URL \
  SUPPORT_OWNER_PASSWORD \
  COMMERCE_OWNER_PASSWORD \
  SUPPORT_APP_PASSWORD \
  COMMERCE_APP_PASSWORD
do
  require_environment "$variable_name"
done

bootstrap_database_url="$POSTGRES_BOOTSTRAP_DATABASE_URL"
unset POSTGRES_BOOTSTRAP_DATABASE_URL

psql \
  --no-psqlrc \
  --quiet \
  --set ON_ERROR_STOP=1 \
  --dbname "$bootstrap_database_url" \
  --file /db/bootstrap.sql
