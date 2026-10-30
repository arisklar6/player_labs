# Policy-lifecycle CLI + API reference

Exact behaviour of the `coworld` commands and Observatory routes this skill uses,
verified against **coworld 0.1.20** (source `Metta-AI/metta`: `packages/coworld/src/coworld/`,
live `coworld <cmd> --help`, and the live `/observatory/openapi.json`). Re-check with
`--help`; the CLI ships ahead of the metta checkout. Auth: `softmax login`
(`load_current_token`); the CLI sends `Authorization: Bearer`, raw API probing uses
`X-Auth-Token`.

## upload — `coworld upload-policy <IMAGE> --name/-n NAME [--run TOK]... [--secret-env K=V]... [--use-bedrock] [--server]`

- `<IMAGE>` = a **local** docker image tag (not a registry URI). The client
  `docker image save`s it, hashes it, and pushes to a Softmax-managed ECR (via raw OCI
  calls — a deliberate workaround for a Docker-29 + ECR bug). Needs a running Docker daemon.
- `--name` (required) = the **stable policy name** the version history hangs off.
  Re-uploading the same name creates a **new version** (server auto-increments `vN`).
- `--run` = argv for images bundling multiple Coworld roles — **must launch your policy**,
  else a reference player runs (silent no-op). Persisted on the version.
- Routes: `POST /v2/container_images/upload` (+ `/complete`) for the image, then
  **`POST /stats/policies/docker-img/complete`** `{name, container_image_id, run?,
  policy_secret_env?}`. Returns `PolicyVersionResponse {id (pv UUID), name, version,
  pools, submit_error}`. CLI prints only `Upload complete: <name>:v<version>`.
- **Inert:** uploading enters no competition. It only registers a version. (`resolve-and-upload`
  is a *Coworld/game* upload wrapper — `POST /v2/coworlds/upload` — **not** a policy flow.)

## submit — `coworld submit <POLICY> --league/-l LEAGUE_ID [--open-browser/...] [--server]`

- `<POLICY>` = `NAME` or `NAME:vN` (bare name → latest owned version). Resolves via
  `GET /stats/policy-versions?mine=true&name_exact=<name>[&version=N]` (you can only submit
  versions **you own**).
- `--league` (required); there is **no `--division`** — placement is server-side.
- Does: **`POST /v2/league-submissions`** `{league_id, policy_version_id}` (schema
  `V2CreateLeagueSubmissionRequest` also allows optional `player_id`, `preferences`,
  `notes` — the CLI exposes none; `player_id` is how to submit as a different owned player). Returns
  `{id (sub_…), status, league_policy_membership_id?}`.
- **Champion is separate.** `submit` creates a submission → async placement → a
  `league_policy_membership` in a division. Becoming champion is a distinct
  server/commissioner action (`POST /v2/league-policy-memberships/{id}/champion`); no CLI
  command does it. So: submit → membership → *maybe* champion later.
- **Reversibility:** `coworld retire-membership <lpm_id> [--reason]` →
  `POST /v2/league-policy-memberships/{id}/retire` retires the placed membership; the
  submission record persists. Treat submit as the irreversible public action.

## monitor — standings (there is **no `coworld standings`**)

| Command | Route | Use |
| --- | --- | --- |
| `coworld memberships --mine [--policy NAME[:vN]] [--active-only] [--champions-only]` | `GET /v2/league-policy-memberships` | **am I active/champion?** rows have `status`, `substatus`, `is_champion`, `division`, `policy_version`, `player` |
| `coworld submissions --mine` | `GET /v2/league-submissions` | submission history + `status` (e.g. `placed`) |
| `coworld results <div_id> [--include-recent-rounds N]` | `GET /v2/divisions/{id}/leaderboard` | **the leaderboard** — `rank`, `player_id`, `player_name`, `score`, `rounds_played`, `recent_rounds[]`. **Ranked per player**, so match your row by `player_id` from your membership. |
| `coworld results <league_id>` | `GET /v2/leagues/{id}/division-ladder` | division ladder |
| `coworld results <round_id>` | `GET /v2/rounds/{id}` | per-round ranked results |
| `coworld leagues [id]` / `coworld divisions [id] [-l league]` | `/v2/leagues`, `/v2/divisions` | resolve current (rotating) league/division ids |

The `monitor` script joins these: submissions (status) + your memberships (champion/status
+ division) + the division leaderboard (rank/score by `player_id`).

## version log — listing uploaded versions

No `coworld versions` command. List every uploaded version for a name via
`GET /stats/policy-versions?mine=true&name_exact=<NAME>&limit=100` → `{entries:[{id,
name, version, created_at}], total_count}` (the `versions` subcommand does this).
`submissions --mine` / `memberships --mine` only show versions you *submitted/placed*, not
every upload. Key the log on `(name, version)` + the version UUID (`id`, immutable).

## Gotchas

- **linux/amd64 mandatory** — `upload-policy` hard-fails on arm64 (build `--platform
  linux/amd64`).
- **`--run` silent fallback** — the quietest failure in the lifecycle; always launch your
  own policy.
- **Rotating ids** — `submit` takes a `league_id`; leaderboards take a `div_id`. Divisions
  rotate; re-resolve live each session (`coworld leagues` → `coworld divisions --league`).
- **Per-player leaderboard** — a version submitted under a different owned player identity
  shows under that player's row/rank; match standings by `player_id`, not name.
- **Auth** — all commands need a current token; 401/403 → `uv run softmax login`.
