# Destination-Agnostic Ingestion Contract

Status: proposed contract for the destination-agnostic ingestion initiative.
It becomes the current operational contract after the target adapters and
validation in `docs/plans/destination-agnostic-ingestion.md` are complete.

## Scope

This contract covers Phase 1 collection and export of the canonical ingest
artifacts. Phase 2 processing remains on the current workstation after export.
Phase 3 database import behavior is unchanged.

The initial collection targets are:

| Shorthand | User-facing term | Execution model |
| --- | --- | --- |
| `local` | Local Docker host | Docker daemon on the current workstation |
| `remote` | Remote Docker host (SSH) | Docker daemon on any SSH-accessible host |
| `fly` | Fly target | Fly Machine using the existing Fly-specific lifecycle |

`remote` is not limited to a LAN. It may be a LAN host, VPN-reachable host,
cloud VM, or other SSH-accessible machine that satisfies the Docker and storage
requirements.

## Common container contract

Every collection target runs the same ingestion image and command contract.

- Container working directory: `/app`
- Code locations:
  - `/app/data_pipeline`
  - `/app/scripts`
- Python import root: `/app`
- Persistent workspace mount: `/app/data`
- Run state: `/app/data/ingest/run_state.json`
- Orchestrator logs: `/app/data/logs/ingest`
- Stage logs: `/app/data/logs/ingest/stages`
- Workspace ownership record: `/app/data/ingest/run_owner.json`
- Runtime target: `INGEST_TARGET` (`local`, `remote`, or `fly`)
- Optional runtime label: `INGEST_RUNTIME_NAME`
- Image Git SHA: `APP_GIT_SHA`
- Image build timestamp: `APP_BUILD_TIMESTAMP`
- Default command:

```text
poetry run python scripts/data_pipeline/run_ingest_pipeline.py
```

The target launcher may add the existing orchestrator options for a fresh run,
resume, or individual stage. It must not replace the stage implementation or
change stage ordering.

The container must receive credentials and runtime settings through environment
injection. Secrets and signed BGG URLs must not be copied into the image.

## Target profile contract

Each target profile must provide or resolve these fields:

- target shorthand: `local`, `remote`, or `fly`;
- execution endpoint:
  - local Docker socket for `local`;
  - SSH host/Docker context for `remote`;
  - Fly app and Machine interface for `fly`;
- image source and identity:
  - build context and tag, or an existing image reference;
  - Git SHA/build timestamp when available;
- persistent workspace:
  - local bind path or named volume;
  - remote-host path or named volume;
  - existing Fly volume mounted at `/app/data`;
- secret source and injection method;
- detached lifecycle operations:
  - start fresh or resume;
  - run one stage;
  - inspect status;
  - retrieve logs;
  - stop or cancel where supported;
- artifact export mechanism and local destination.

The host-side storage path is target-specific. The container must only depend on
the `/app/data` path.

## Persistent artifact contract

Collection writes the following artifacts beneath `/app/data/ingest` inside the
container:

| Artifact | Container path | Local processing destination |
| --- | --- | --- |
| Rankings | `/app/data/ingest/ranks/boardgame_ranks_*.csv` | `data/ingest/ranks/` |
| Game data | `/app/data/ingest/game_data/boardgame_data_*.duckdb` | `data/ingest/game_data/` |
| Ratings | `/app/data/ingest/ratings/boardgame_ratings_*.duckdb` | `data/ingest/ratings/` |

State and logs are also persistent workspace data but are not part of the
Phase 2 artifact export unless explicitly requested for diagnostics.

Export behavior must satisfy these rules:

- export is explicit, not automatic;
- the operator identifies the completed or selected run/artifact set;
- remote exports can resume after interruption;
- final files are promoted only after size and checksum verification;
- exports land in the existing local directories without changing Phase 2
  commands;
- an export must not silently replace an unrelated artifact set.

## Execution and processing targets

The execution target is where the collection container runs. The processing
target is initially always the current workstation.

Examples:

```text
local execution  -> export/copy to current workstation -> Phase 2 locally
remote execution -> SSH export to current workstation  -> Phase 2 locally
fly execution    -> Fly artifact download              -> Phase 2 locally
```

This separation allows the current workstation to start and later retrieve a
detached run without remaining powered on while a remote or Fly container is
working.

## Run ownership and concurrency

Only one collection run may operate on a given persistent workspace at a time.
The target launcher must reject a second run when an active run or valid lock is
present, regardless of whether the first run was started through `local`,
`remote`, or `fly`.

The ownership record must identify, at minimum:

- run ID;
- target shorthand;
- image identity;
- start time in UTC;
- host/container or Machine identity when available.

Recovery of stale ownership must be an explicit operator action after checking
the target status. A normal resume must not silently take over a live run.

Separate target workspaces may be used when operators intentionally run
independent datasets, but a workspace must never be shared concurrently.

The provider-neutral operator uses the ownership record as an exclusive file
created before a collection command starts. Normal container exit releases the
record. If a container is terminated before cleanup, the operator must inspect
the target status and explicitly clear the stale record before retrying; a
normal resume must not clear it automatically.

The initial common command surface is:

```text
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

Local Docker uses the repository `data/` directory by default. Remote Docker
uses the named volume `bg-lib-ingest-data` by default; a remote bind workspace
must be supplied as an absolute path with
`--remote-workspace-type bind`. Remote Docker uses
`INGEST_REMOTE_DOCKER_HOST` or `--remote-host` and the existing SSH-backed
Docker connection.

The common export command uses the same resumable, chunked transfer behavior
for local Docker, remote Docker, and Fly. It verifies each chunk size and the
assembled artifact's SHA-256 before atomically promoting the final file. A
failed or interrupted transfer leaves the `.parts` directory for a later
resume; successful transfers remove it unless `--keep-parts` is supplied.

## Image identity

Every run should report the image/source identity when available:

- Git SHA;
- build timestamp;
- image tag or digest when available;
- target shorthand.

The existing `APP_GIT_SHA` and `APP_BUILD_TIMESTAMP` image metadata are the
starting point for this contract. Fly-specific app names may remain in Fly
notifications, but the shared status and run records must not require a Fly app
name.

## Target-specific requirements

### Local Docker host

- Docker is installed and usable by the operator.
- `/app/data` maps to a local bind path or named volume.
- Credentials are injected from the local environment or an env file without
  being committed.
- Artifact export copies verified files into the current checkout.

### Remote Docker host (SSH)

- The host is reachable over SSH.
- The SSH account can operate the Docker daemon.
- The host has durable storage for `/app/data`.
- Remote bind paths are resolved on the remote host, never assumed to be paths
  on the current workstation.
- The container can continue after the initiating SSH session disconnects.
- Artifact export transfers verified files back to the current workstation.
- Docker's unauthenticated network API is not required or exposed.

### Fly target

- The existing `flyctl`-based lifecycle remains supported.
- `fly.ingest.toml` continues to provide the image build, VM sizing, restart
  policy, environment, and volume mount.
- Fly secrets remain managed through Fly's secret store.
- The existing Fly maintenance, run, log, and artifact operations remain
  available through the compatibility adapter.

## Authoritative references

- Workflow and artifact handoff: `data_pipeline/README.md`
- Orchestrator behavior: `scripts/data_pipeline/README.md`
- Current Fly operator behavior: `scripts/ingest/README.md`
- Current image contract: `Dockerfile.ingest`
- Current Fly runtime: `fly.ingest.toml`
- Implementation sequence: `docs/plans/destination-agnostic-ingestion.md`
