# RESTORE RUNBOOK

Operator procedure. Assumes a clean machine with Postgres.app and the repository checked out.

---

## 0 · Preconditions

```bash
export PATH="/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"
pg_ctl -D ~/Library/Application\ Support/Postgres/var-17 -l /tmp/pg.log start
psql -U peterluro -lqt | cut -d'|' -f1 | head
```

## 1 · Select a bundle

```bash
ls -1dt ~/mip_backups/* | head -5
B=$(ls -1dt ~/mip_backups/* | head -1)
cat "$B/MANIFEST.txt"        # confirm commit and timestamp before proceeding
```

## 2 · Verify integrity FIRST

```bash
( cd "$B" && shasum -a 256 -c CHECKSUMS.sha256 )
```
**Any line not `OK` → stop. Do not restore from a bundle that fails checksum.**

## 3 · Restore to a disposable database

```bash
cd /Users/peterluro/Desktop/stock_scoring
REPO=$PWD ./tools/ops/restore.sh "$B" mip_restore_drill
```
The script refuses `mip` as a target by design. To promote a verified restore, dump from the drill
database and load deliberately — never restore straight over live.

## 4 · If no dump exists — rebuild the schema

```bash
createdb -U peterluro mip_rebuild
MIP_DATABASE_URL="postgresql+psycopg://peterluro@localhost:5432/mip_rebuild" \
  uv run alembic upgrade head
psql -U peterluro -d mip_rebuild -tAc \
  "select count(*) from information_schema.tables where table_schema='public'"
# expected: 86
```

## 5 · Verify the restore

```bash
# tables
psql -U peterluro -d mip_restore_drill -tAc \
  "select count(*) from information_schema.tables where table_schema='public'"

# artifacts byte-compare (workdir path printed by restore.sh)
W=$(cat /tmp/mip_restore_workdir)
diff -rq "$W/data/validation" data/validation && echo "validation artifacts identical"
diff -rq "$W/docs/phase1"     docs/phase1     && echo "phase1 contract identical"

# study contract still verifies
python3 tools/phase1/verify_reports.py   # expect exit 0
```

## 6 · Acceptance criteria

| Check | Expected |
|---|---|
| Checksums | 7/7 OK |
| Tables after restore | matches source |
| Tables after rebuild-from-migrations | **86** |
| Validation artifacts | byte-identical |
| Phase 1 contract | byte-identical |
| `verify_reports.py` | **exit 0** |

## 7 · Teardown

```bash
dropdb -U peterluro --if-exists mip_restore_drill
rm -rf "$(cat /tmp/mip_restore_workdir)"
```

## 8 · Escalation

| Symptom | Action |
|---|---|
| Checksum mismatch | Bundle corrupt. Use the previous bundle. Investigate the storage medium |
| `pg_restore` errors | Continue — `--no-owner` warnings are normal. Verify table count |
| Table count ≠ 86 after rebuild | Migration chain broken. Verify head with the chain-walk script in the audit |
| `verify_reports.py` ≠ 0 | The study contract has drifted. **Stop. Do not proceed to any gate** |
