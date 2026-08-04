#!/usr/bin/env bash
# Stage 0 minimum backup control. Produces a checksummed, restorable bundle.
set -euo pipefail
export PATH="/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"

REPO="${REPO:-/Users/peterluro/Desktop/stock_scoring}"
DEST="${BACKUP_DEST:-$HOME/mip_backups}"
DB="${DB:-mip}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DEST/$TS"
mkdir -p "$OUT"

echo "[backup] $TS -> $OUT"

# 1 schema + data (custom format, restorable with pg_restore)
if psql -U peterluro -lqt | cut -d'|' -f1 | grep -qw "$DB"; then
  pg_dump -U peterluro -Fc -f "$OUT/${DB}.dump" "$DB"
  echo "[backup]   db dump: $(du -h "$OUT/${DB}.dump" | cut -f1)"
else
  echo "[backup]   WARNING: database '$DB' not found — dump skipped" | tee "$OUT/DB_MISSING.txt"
fi

# 2 immutable raw + research artifacts
tar -czf "$OUT/validation.tar.gz" -C "$REPO" data/validation
tar -czf "$OUT/reports.tar.gz"    -C "$REPO" data/reports
tar -czf "$OUT/rawcsv.tar.gz"     -C "$REPO" --exclude='data/validation' --exclude='data/reports' data
tar -czf "$OUT/phase1.tar.gz"     -C "$REPO" docs/phase1
tar -czf "$OUT/code.tar.gz"       -C "$REPO" src alembic tools docs/v4 docs/program

# 3 provenance
{ echo "utc=$TS"; echo "repo=$REPO"; echo "db=$DB";
  echo "git_commit=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo NA)";
  echo "git_dirty=$(git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')";
  echo "alembic_head=$(ls "$REPO"/alembic/versions/*.py | wc -l | tr -d ' ') migrations";
} > "$OUT/MANIFEST.txt"

# 4 checksum every artifact
( cd "$OUT" && shasum -a 256 * > CHECKSUMS.sha256 )
echo "[backup] artifacts: $(ls -1 "$OUT" | wc -l | tr -d ' ')  total: $(du -sh "$OUT" | cut -f1)"
echo "[backup] OK $OUT"
