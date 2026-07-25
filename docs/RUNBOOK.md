# MIP Runbook — Daily Operation

Short operational guide for running the platform from a cold start.

## 1. Start Postgres (only if not already running)

Postgres.app does **not** run as a background service, so after a reboot you
start it manually:

```bash
/Applications/Postgres.app/Contents/Versions/17/bin/pg_ctl -D "$HOME/Library/Application Support/Postgres/var-17" start
```

## 2. Verify Postgres is up

```bash
/Applications/Postgres.app/Contents/Versions/17/bin/pg_ctl -D "$HOME/Library/Application Support/Postgres/var-17" status
```

Expected: `pg_ctl: server is running (PID: …)`. If it says *no server running*,
run step 1.

## 3. Verify the `mip` database is reachable and seeded

```bash
/Applications/Postgres.app/Contents/Versions/17/bin/psql -U peterluro -h localhost -d mip -c "select count(*) from instruments;"
```

Expected: a count (e.g. `78`). If this errors, Postgres isn't up (step 1) or the
DB isn't migrated (`uv run mip db upgrade`).

## 4. Run the daily update

Always run from the project directory (`~/Desktop/stock_scoring`).

Preview what it will do, without writing anything:

```bash
uv run mip update --dry-run
```

Run the real daily update (prices → macro → fundamentals → earnings → features →
portfolio → assess → reports → archive → evaluate):

```bash
uv run mip update
```

Notes:
- It self-resolves the last **completed** NYSE session. Run it after the close to
  ingest today; mid-session it uses the last completed bar.
- It won't re-run a market date it already completed — force a re-run with:

```bash
uv run mip update --force
```

- If a run failed partway, resume it (get `RUN_ID` from step 5):

```bash
uv run mip update --resume RUN_ID
```

## 5. Check what happened

```bash
uv run mip runs list
```

Shows recent ingestion runs with status (`success` / `partial` / `failed`) and
counts. Latest reports are written under `data/reports/latest/` and
`data/reports/<date>/`.

## First-time-only setup (already done on this machine)

Only needed on a fresh checkout — your `mip` DB already has all of this:

```bash
uv sync && uv run mip db upgrade && uv run mip universe seed && uv run mip calendar build
```

Then an initial ingest + `uv run mip features build --all` and a portfolio
import. Day-to-day you never repeat these — only steps 1–5 above.
