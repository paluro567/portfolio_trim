#!/usr/bin/env bash
# Stage 0 restore. Rebuilds into a DISPOSABLE database. Never targets 'mip'.
set -euo pipefail
export PATH="/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"

SRC="${1:?usage: restore.sh <backup_dir> [target_db]}"
TARGET="${2:-mip_restore_drill}"
[ "$TARGET" = "mip" ] && { echo "REFUSING to restore over the live 'mip' database"; exit 2; }

echo "[restore] source=$SRC target=$TARGET"
echo "[restore] verifying checksums..."
( cd "$SRC" && shasum -a 256 -c CHECKSUMS.sha256 ) || { echo "[restore] CHECKSUM FAILURE"; exit 1; }

dropdb -U peterluro --if-exists "$TARGET"; createdb -U peterluro "$TARGET"
if [ -f "$SRC/mip.dump" ]; then
  pg_restore -U peterluro -d "$TARGET" --no-owner "$SRC/mip.dump" 2>&1 | tail -2 || true
  echo "[restore]   restored from dump"
else
  echo "[restore]   no dump present — rebuilding schema from migrations"
  MIP_DATABASE_URL="postgresql+psycopg://peterluro@localhost:5432/$TARGET" \
    uv run --directory "${REPO:-/Users/peterluro/Desktop/stock_scoring}" alembic upgrade head 2>&1 | tail -1
fi

WORK="$(mktemp -d)"
for t in validation reports rawcsv phase1 code; do
  [ -f "$SRC/$t.tar.gz" ] && tar -xzf "$SRC/$t.tar.gz" -C "$WORK"
done
echo "[restore] artifacts extracted to $WORK"
echo "[restore] tables in $TARGET: $(psql -U peterluro -d "$TARGET" -tAc "select count(*) from information_schema.tables where table_schema='public'")"
echo "$WORK" > /tmp/mip_restore_workdir
echo "[restore] OK"
