# Fly Ingest Commands

Use `scripts/ingest/fly_ingest.sh` as the operator interface for the dedicated
Fly ingest machine. Each run command changes the machine's single process
command, starts it, and lets the machine stop when the command finishes. The
stage output remains in the normal Fly application logs.

## Maintenance

Maintenance is only for SSH inspection or manual work. It must not overlap an
ingest run.

```bash
scripts/ingest/fly_ingest.sh maintenance start --for 4h
scripts/ingest/fly_ingest.sh maintenance status
scripts/ingest/fly_ingest.sh machine shell
scripts/ingest/fly_ingest.sh maintenance stop
```

Maintenance mode requires a finite lease and defaults to four hours. The
maximum lease is twelve hours. When the lease expires, the maintenance process
exits and `restart.policy = "never"` stops the machine. `maintenance stop`
stops the machine before disabling maintenance mode. Run commands refuse to
start while maintenance mode is active.

## Runs

```bash
scripts/ingest/fly_ingest.sh run ranks       # rankings only
scripts/ingest/fly_ingest.sh run game-data   # requires completed rankings
scripts/ingest/fly_ingest.sh run ratings     # requires completed game data
scripts/ingest/fly_ingest.sh run fresh       # all stages, new state and data
scripts/ingest/fly_ingest.sh run resume      # first incomplete stage onward
```

Individual stage commands update only their requested stage in
`run_state.json`. A later `run resume` continues with the next incomplete
stage. Each stage retries twice after its initial attempt; after three total
attempts it is marked failed and the machine stops.

`run ranks` may run regardless of the other stage states. `run game-data`
requires rankings to be completed, and `run ratings` requires game data to be
completed. The local terminal does not need to remain open.

## Operations

```bash
scripts/ingest/fly_ingest.sh machine status
scripts/ingest/fly_ingest.sh deploy             # only when code/config changed
scripts/ingest/fly_ingest.sh secrets sync       # after .env secret changes
scripts/ingest/fly_ingest.sh resize --memory 8192
scripts/ingest/fly_ingest.sh logs
```

The `logs` command fetches the current buffered logs once, writes them to a
timestamped file under `logs/deploy/`, and exits. It does not follow new logs
or print log contents to standard output.

## Artifact export

```bash
scripts/ingest/fly_ingest.sh maintenance start --for 4h
scripts/ingest/fly_ingest.sh artifacts list
scripts/ingest/fly_ingest.sh artifacts download \
  --remote-path /app/data/ingest/ratings/boardgame_ratings_<timestamp>.duckdb \
  --chunk-mb 256
scripts/ingest/fly_ingest.sh maintenance stop
```
