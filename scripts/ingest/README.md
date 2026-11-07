# Ingestion Commands

Use `scripts/ingest/ingest.sh` as the target-neutral operator interface when
choosing where the collection container runs. Use
`scripts/ingest/fly_ingest.sh` for Fly-specific maintenance, deployment,
secrets, and compatibility operations. Each Fly run command changes the
machine's single process command, starts it, and lets the machine stop when the
command finishes. The stage output remains in the normal Fly application logs.

## Common target interface

Use `scripts/ingest/ingest.sh` when choosing where the collection container
runs. The processing target remains the current workstation after explicit
artifact export.

| Target | User-facing term | Required connection/storage |
| --- | --- | --- |
| `local` | Local Docker host | Local Docker daemon and durable local workspace |
| `remote` | Remote Docker host (SSH) | SSH access, Docker permission, and durable remote storage |
| `fly` | Fly target | Fly app, mounted volume, and Fly-managed secrets |

Common commands:

```bash
scripts/ingest/ingest.sh --target <local|remote|fly> build
scripts/ingest/ingest.sh --target <local|remote|fly> run <ranks|game-data|ratings|fresh|resume>
scripts/ingest/ingest.sh --target <local|remote|fly> status
scripts/ingest/ingest.sh --target <local|remote|fly> logs [--follow]
scripts/ingest/ingest.sh --target <local|remote|fly> stop
scripts/ingest/ingest.sh --target <local|remote|fly> list
scripts/ingest/ingest.sh --target <local|remote|fly> export \
  --remote-path <path> [--output-dir <dir>] [--chunk-mb <mb>] \
  [--keep-parts] [--overwrite]
```

For `local` and `remote`, the `logs` command writes Docker output to a
timestamped file under `logs/deploy/` and prints only the file path. It never
streams application logs to the terminal. The `fly` target uses the same
file-oriented behavior through its Fly log capture command.

Target-specific options are supplied before the command:

```text
--image <tag>                         image to build or run
--env-file <path>                     local secret/runtime input
--local-workspace <path>              local bind source for `local`
--remote-host <ssh-host>              SSH-backed Docker endpoint for `remote`
--remote-workspace <name-or-path>     remote volume or host path
--remote-workspace-type volume|bind   remote workspace storage type
```

When a dotenv env file is selected for `local` or `remote`—through
`--env-file`, `INGEST_ENV_FILE`, or the default repository `.env`—the launcher
parses it with the repository's dotenv parser before starting Docker.
Surrounding quotes are therefore treated as dotenv syntax rather than becoming
part of values inside the container. Parsed values are injected through
Docker's inherited environment interface; the source `.env` file is not
modified and no temporary env file is created.

For `local`, the default workspace is the repository `data/` directory. For
`remote`, the default is the named volume `bg-lib-ingest-data`; a bind workspace
must be an absolute path on the remote host. Set `INGEST_REMOTE_DOCKER_HOST`
in the shell before running remote commands, or pass `--remote-host` on each
command. The value uses the Docker SSH endpoint form:

```bash
export INGEST_REMOTE_DOCKER_HOST="ssh://user@example-host"
ssh user@example-host docker info
```

If SSH keys are already configured, load the key into an agent to simplify
repeated commands. Replace the example path with your key path:

```bash
eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_thenovo_nuc
```

The SSH account must be able to operate Docker. For a one-off command, use
`--remote-host "ssh://user@example-host"` instead of the exported variable.
`INGEST_LOCAL_WORKSPACE`, `INGEST_REMOTE_WORKSPACE`, and
`INGEST_REMOTE_WORKSPACE_TYPE` provide corresponding defaults.

The collection container keeps state, logs, and artifacts under `/app/data`.
Export is never automatic. The operator selects the completed artifact path,
and the common exporter verifies size and SHA-256 before promoting the local
file. Phase 2 processing commands remain unchanged and run on the current
workstation.

The `fly` target delegates to the compatibility commands documented below;
Fly-specific maintenance, secrets, deployment, and machine behavior remain in
this document.

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
