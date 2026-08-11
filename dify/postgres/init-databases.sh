#!/bin/bash
# Create the plugin-daemon database on first PostgreSQL init only.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
CREATE DATABASE dify_plugin;
EOSQL
