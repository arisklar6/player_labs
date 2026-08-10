# Crewrift user preferences

Durable preferences the human has expressed **specifically for Crewrift work** —
layered on top of the lab-wide [`../user_preferences.md`](../user_preferences.md)
(read that too; it holds the game-agnostic preferences). [`AGENTS.md`](AGENTS.md)
tells you to **read this on startup**.

When the human states a Crewrift-specific preference (explicitly, or clearly through
repeated correction), **record it here** as a short, concrete entry so it persists
across sessions. Keep it tidy: one bullet per preference, drop superseded ones.
General (non-Crewrift) preferences go in the lab-wide file instead.

## Working context

- **Active policy under optimization: `crewborg`** (chosen 2026-08-10). Future
  sessions: continue improving this policy unless the user says otherwise.
- League: Crewrift Prime `league_a12f5172-0907-4d04-8bcb-ca02f5360e3a`
  (Coworld `cow_772561cb-b2f0-46b1-ab8c-6ef7627970e0`, division
  `div_acbde92a-df21-4489-859c-4510bd4445f2`).

## Environment notes

- `uv sync` fails on a fresh clone: the `players` git dependency carries a submodule
  (`users/relh/co-gas` → `git@github.com:Metta-AI/co-gas.git`) that is private/404 for
  users outside Metta-AI. Workaround — skip that submodule, e.g. prefix commands that
  resolve git deps with:
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=submodule.users/relh/co-gas.active GIT_CONFIG_VALUE_0=false`
  Filed as https://github.com/Metta-AI/coworld/issues/36
- **Hosted results + policy logs are 403 for non-Softmax accounts**
  (`{"detail":"User is not a softmax team member"}` on `/jobs/{id}/artifacts/results` and
  `/jobs/{id}/policy-logs`). So `crewrift-report`'s `report.py` and `profile_replay.py`
  cannot run on hosted episodes, and Tier-3 trace analysis is unavailable. Replays *are*
  public (via the episode's `replay_url`), and `episode.json` carries
  `participant_scores` (seat → score), `participants` (seat → policy/owner) and
  `game_config.slots` (forced roles) — enough to rebuild the role-split report from
  `expand_replay` output alone. Local `smoke.py` runs DO produce policy logs.
  Filed as https://github.com/Metta-AI/coworld/issues/37
- **`build_expand_replay.sh` needs `nimby`**, which isn't in the prerequisites:
  `nimble install -y nimby`, then `export PATH="$HOME/.nimble/bin:$PATH"`.
- **`coworld` 0.1.20 is too old for the live manifest** — `run-episode` rejects it with
  `Additional properties are not allowed ('tags'/'replay_viewer' was unexpected)`, so the
  Gate-1 smoke test fails before starting. Fixed by
  `uv lock --upgrade-package coworld && uv sync` (0.1.20 → 0.1.38); smoke then passes.
- **`smoke.py --run` needs `=` syntax** (`--run=python --run=-m --run=...`); the
  space-separated form in the skill doc makes argparse eat `-m` as a flag.

## Preferences

_None recorded yet._
</content>
