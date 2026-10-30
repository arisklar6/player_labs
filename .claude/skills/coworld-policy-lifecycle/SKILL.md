---
name: coworld-policy-lifecycle
description: "Use to take a built player image through the Coworld policy lifecycle: upload it as a new version, (gated) submit it to a league, and monitor its live standings. Triggers: 'upload the new policy version', 'submit crewborg to the league', 'is my submission live / champion', 'how is my policy ranking', 'ship the player'. Game-agnostic. Upload is routine and inert; SUBMIT is the public, irreversible, champion-making action — only on explicit human go-ahead."
---

# Coworld Policy Lifecycle (upload → submit → monitor)

Take a built player image through its competitive lifecycle. **The upload/submit
distinction is load-bearing:**

- **`upload-policy` is routine and inert** — it registers a **new version** of a stably
  named policy and pushes the image; nothing competes. This is the **Gate-1 re-upload**
  you do every iteration. Do it freely.
- **`submit` is the public, gated, effectively-irreversible action** — it injects a
  version into a live league, where it can become the **champion** as soon as it
  qualifies. This is **Gate 2**: only submit once the player is demonstrably better and
  the human has given explicit go-ahead. *Not* submitting is your rollback.

**Announce at start:** "Working the policy lifecycle. Uploading a new version" — or, for
submission — "this submits to the live league (Gate 2); confirming go-ahead first."

## Workflow

1. **Build `linux/amd64`** (game-specific) and **upload it as a new version** (routine,
   ungated). Pass `--run` so the runner launches *your* policy:

   ```bash
   uv run coworld upload-policy <your-tag>:dev --name <policy-name> [--run python --run -m --run my_player]
   # -> "Upload complete: <name>:v<N>"   (a new version; INERT, not competing)
   ```
   Re-uploading the **same `--name`** auto-increments the version. Record the new version
   in the **version log** (next section).

2. **Smoke-test before relying on it** — local Gate-1 via the `coworld-local-run` skill,
   or just confirm the upload returned a new `vN`. **Evaluate competitiveness via
   experience requests** (`coworld-experience-requests`) against this uploaded version —
   uploading does *not* enter any competition, so you can iterate uploads + experiments
   freely without touching a league.

3. **Submit — only when better + the human approves (Gate 2):**

   ```bash
   uv run coworld submit <policy-name>[:vN] --league <league_id>
   ```
   Creates a league submission (`POST /v2/league-submissions`); the server then places it
   asynchronously into a division (a membership). **Becoming champion is a separate
   server/commissioner step** — `submit` does not set it. Re-resolve the `league_id`
   live (`coworld leagues`); ids rotate.

4. **Monitor standings** — is it active/champion, and how is it ranking?

   ```bash
   cd /path/to/player_labs   # the repo root
   uv run python .claude/skills/coworld-policy-lifecycle/scripts/policy_lifecycle.py \
     monitor --name <policy-name>
   ```
   Prints each submission's status, each membership's `status`/champion flag/division,
   and the version's **rank + score** on the live division leaderboard (matched per
   player). Or by hand: `coworld memberships --mine --policy <name>` (am I champion?) +
   `coworld divisions --league <id>` → `coworld results <div_id> --include-recent-rounds 5`.

## The version log (a best practice — keep it)

Maintain a log mapping **each uploaded version → the change it carries**, so you always
know what each version is testing/capable of (see `best_practices.md`). There is no
`coworld versions` command; reconcile your log against the live list:

```bash
uv run python .claude/skills/coworld-policy-lifecycle/scripts/policy_lifecycle.py \
  versions --name <policy-name>     # every uploaded version: vN + UUID + created_at
```

Key the log on `(name, version)` for readability with the policy-version UUID as the
canonical id. The version log itself is **game-specific** (it describes that player's
changes) — keep it under that player's lab dir, not at the lab root.

## Notes & gotchas

- **`--run` is the quietest failure.** For an image bundling multiple roles, you must
  pass `--run` with the argv that launches *your* policy on both `upload-policy` and
  local runs — omit it and a reference/default player runs, so the version uploads/submits
  fine but a *different* policy actually plays.
- **Reversibility:** `coworld retire-membership <lpm_id> [--reason ...]` retires a placed
  membership (`POST /v2/league-policy-memberships/{id}/retire`); the public submission
  record persists. Treat `submit` as irreversible when deciding to do it.
- **Attribution:** the CLI `submit` always submits as the account default player. To
  submit under a *different* owned player identity, call `POST /v2/league-submissions`
  with the API's `player_id` field (not exposed by the CLI; see `references/cli.md`).
- **`resolve-and-upload` is NOT this flow** — it's a Coworld/*game* upload wrapper, not a
  policy one. Don't use it for policies.
- **amd64 mandatory** (hard fail on upload); rotating league/division ids (re-resolve);
  Docker daemon needed for the push; `submit` only resolves versions you own (`--mine`).
- Full CLI + API reference (exact flags, routes, response shapes): `references/cli.md`.
  Verified against **coworld 0.1.20**. Live manifests now need a newer client: under 0.1.20, `run-episode` rejects them (`'tags'/'replay_viewer' was unexpected`); upgrade with `uv lock --upgrade-package coworld && uv sync` (0.1.38 worked).
