> Scope: Crewrift-specific rules for crewrift_lab/ (layered on the lab-root AGENTS.md).

# crewrift_lab — agent guide

The **Crewrift** corner of player_labs: where we build, evaluate, and improve
**player policies** for the Crewrift game. This file orients agents working here.

**Read the lab-root [`../AGENTS.md`](../AGENTS.md) first** — it defines the
improvement loop, your role in it, the two gates, and the game-agnostic skills.
This file is the **Crewrift-specific layer** on top of it: the game, the docs, the
practices/preferences, and the policies we optimize. When the two disagree, the root
defines *process*; this file defines *Crewrift*.

## Hard constraints

- **Mandatory LLM profile.** Crewrift LLM agents must use Haiku 4.5
  (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) and stay below 1,800
  quota-weighted tokens per policy episode, cumulative across all calls
  (input + cache-write + 5 × output tokens). If the remaining budget cannot
  cover another call, use a deterministic fallback.

## What Crewrift is

Crewrift is a Coworld **social-deduction game** (an *Among Us*–style benchmark):
8–16 players on a 2-D map. Most are **crewmates** completing tasks; a few are
**imposters** who kill crewmates and blend in. Bodies get reported, meetings are
called, players chat and **vote** someone out. Crew win by finishing all tasks or
voting out every imposter; imposters win by killing enough crew. Player policies
speak the binary **Sprite-v1** protocol over a websocket — they receive the rendered
scene and act with a d-pad + A/B, with **no semantic action API**.

For the full game — rules, roles, win conditions, scoring, flow, and strategy from a
**gameplay** perspective — read [`docs/crewrift-gameplay.md`](docs/crewrift-gameplay.md)
(the lab's self-contained game reference; you rarely need to leave the repo). The game
source in the `Metta-AI/coworld-crewrift` repo remains the ultimate authority on rules
and the scene vocabulary. The policies we build and optimize are listed in the
[Player policies](#player-policies) index below.

## The loop, in Crewrift terms

The root loop (evaluate → report → direction → implement → gate1+rebuild+reupload →
repeat → gate2 → submit) runs **unchanged** here. The Crewrift-specific instruments:

- **Evaluate** (step 1) — experience requests against the uploaded version of the
  policy under optimization. **Decompose by role** (crewmate vs. imposter are
  effectively two different policies; see best practices) and by opponent. To pin the
  requester's role, set `game_config_overrides.slots` — shape in
  [`docs/crewrift-gameplay.md` → Forcing roles in evaluations](docs/crewrift-gameplay.md).
- **Report** (step 2) — pull artifacts, then turn the batch into a dense report with
  the **`crewrift-report`** skill (flags the interesting episodes by role, profiles
  them). It builds on the Crewrift readers in
  [`docs/crewrift-replays.md`](docs/crewrift-replays.md): the objective
  `expand_replay` event timeline (version-matched via
  [`tools/build_expand_replay.sh`](tools/build_expand_replay.sh)) **and** the policy's
  own subjective per-tick logs, aligned by tick.
- **Implement** (step 4) — change the policy under optimization (see the
  [Player policies](#player-policies) index; each vendored policy carries its own
  internal docs).
- **Gate 1 / rebuild / upload / submit** (steps 5–8) — build the policy's image
  in-lab with [`tools/build_player.sh <policy>`](tools/build_player.sh) (Docker-only;
  design in [`docs/designs/building_players.md`](docs/designs/building_players.md)), then
  the game-agnostic skills + [`../player-build.md`](../player-build.md) for the
  upload/submit flow. The Crewrift I/O contract any built image must satisfy is
  [`docs/crewrift-player.md`](docs/crewrift-player.md).

## Crewrift lab docs

- **[`docs/crewrift-gameplay.md`](docs/crewrift-gameplay.md)** — the game itself, from
  a **gameplay** (not implementation) perspective: rules, roles, win/loss, flow,
  mechanics, scoring, and a full strategy treatment. The self-contained game reference
  — start here to build a mental model before reasoning about play or setting direction.
- **[`docs/crewrift-player.md`](docs/crewrift-player.md)** — what **any** Crewrift
  player policy must do: the Sprite-v1 I/O contract (decode the scene, decide, emit
  buttons/chat), the scene vocabulary, phases, scoring. For building a new policy or
  understanding the contract every policy implements.
- **[`docs/crewrift-replays.md`](docs/crewrift-replays.md)** — reading a *finished*
  Crewrift game: the visual replay, `expand_replay`'s objective event timeline, a
  policy's subjective trace logs, and the `.bitreplay` format. The "Report" step's
  signal-extraction reference.
- **[`docs/designs/building_players.md`](docs/designs/building_players.md)** — how we build
  player images in-lab (Plan A: Docker-only, central game-ref pin). A general-case
  section (for building *any* Crewrift player, vendored or not) followed by the
  per-policy specifics. The build code is `tools/build_player.sh` +
  `tools/versions.env`.

Vendored policies also carry their own internal docs (design/architecture) under
their directory — see the [Player policies](#player-policies) index.

## Skills

Crewrift-specific skills live here in `.claude/skills/`:

- **`crewrift-report`** — turn a **set** of episodes (an experience request, a
  policy's recent league games, a tournament batch) into a dense, role-decomposed
  report of a policy's strengths/weaknesses: it flags the "interesting" episodes
  (score outliers, role-objective failures, killed-vs-ejected, voting pathologies,
  ops failures) and profiles them via `expand_replay`. The analysis engine of the
  loop's **Report** step. `scripts/report.py` (Tier 1, structured) +
  `scripts/profile_replay.py` (Tier 2, replay timeline); `references/signals.md`.
- **`crewrift-ab`** — **A/B test two policy versions head-to-head** along an axis you
  choose: run both in **matched, fresh** experience requests (same roster/roles/count,
  same window — so the delta is attributable, not confounded by league drift), then
  compare hard metrics (`scripts/compare.py` — role-split deltas with significance + a
  regression scan) **and** run a context-driven qualitative investigation of the two
  sides' logs/replays. Use it whenever you need to know whether one version genuinely
  beats another on something — confirming a change helped, chasing a suspected
  regression, settling "is A or B better at X," testing a hypothesis. (Distinct from
  `crewrift-report`, which surveys *one* batch descriptively; A/B is a *targeted
  two-version* comparison.)
- **`crewrift-diagnose`** — turn a report's signals into **evidence-grounded,
  mechanistic improvement hypotheses**: investigate the replays/logs/code for *why* a
  behavior happens (or fails to), then **present candidate directions to the human** as
  options (not directives). An optional augmentation of the **direction** step — it
  enriches the human's call, doesn't replace it. Multi-turn/agentic (and will turn up
  tracing + re-run on its own if the logs are too thin). Pairs with `crewrift-report`
  (signals in) and `crewrift-ab` (test a hypothesis's predicted effect).

The loop's **game-agnostic** halves (experience requests, artifact download, local
run, policy lifecycle) live at the **lab root** (`../.claude/skills/`, indexed in
[`../AGENTS.md`](../AGENTS.md)) — use those to *create* and *pull* the episodes, then
`crewrift-report` to analyze them. New Crewrift-specific tooling belongs here, not at
the root.

## Crewrift best practices

[`best_practices.md`](best_practices.md) holds Crewrift-specific practices layered on
top of the root [`../best_practices.md`](../best_practices.md) — things that are true
of *this game's* tooling and failure modes (replay version-skew, role decomposition,
trace-level verification). **Read both**; root first.

## Crewrift user preferences

[`user_preferences.md`](user_preferences.md) records the human's durable preferences
**specific to Crewrift work**, layered on the root
[`../user_preferences.md`](../user_preferences.md). **Read both on startup**, and when
the human states a Crewrift-specific preference, record it here.

## Deferred tasks

Crewrift-specific parked work lives in the **shared** [`../TODO.md`](../TODO.md)
alongside the rest of the lab's deferred tasks (there's no separate Crewrift TODO).
Check it at the start of focused work.

## Player policies

The Crewrift player policies we've vendored, each a drift-able in-lab copy, and each
**buildable in-lab** with `tools/build_player.sh <policy>` (see
[`docs/designs/building_players.md`](docs/designs/building_players.md)). They come in two
flavors: **crewborg is Python** (editable-installed for dev; image installs the SDK +
fork); **notsus and suspectra are Nim** (their image clones the crewrift game at the
pinned `CREWRIFT_REF` and compiles). All repos are public, so **every build is
Docker-only with no credentials**.

- **crewborg** *(Python)* — at [`crewrift/crewborg/`](crewrift/crewborg/) (package
  `crewrift.crewborg`), a drifting fork of upstream `Metta-AI/players`
  (`players/crewrift/crewborg`). A full Python player: `perception/`
  (Sprite-v1 → scene decoder), `strategy/`, `modes/`, `action.py`, `coworld/`
  (the bridge). Imports the shared `players.player_sdk` from the **pinned public
  `players` repo** (`pyproject.toml`; no local checkout). Its own
  [`AGENTS.md`](crewrift/crewborg/AGENTS.md) and
  [`design.md`](crewrift/crewborg/design.md) map its internals. **Currently the
  primary policy under optimization.**
- **notsus** *(Nim)* — at [`crewrift/notsus/`](crewrift/notsus/), the **reference
  baseline** (upstream lives in the game repo,
  `Metta-AI/coworld-crewrift`: `players/notsus/`; public image
  `…/players/notsus:latest`). The minimal Sprite-v1 implementation
  (`notsus.nim` + `notsus/{votereader,protocols}.nim`), with its Dockerfile and
  `coplayer_manifest.json`. Useful as a comparison opponent and a from-scratch
  starting point. (The prebuilt `notsus.out` binary is **not** vendored.)
- **suspectra** *(Nim + Python LLM hook)* — at
  [`crewrift/suspectra/`](crewrift/suspectra/), a fork of notsus
  (`suspectra.nim`) that adds evidence voting and a bounded Bedrock/Anthropic
  **meeting LLM** (`llm_meeting.py`, invoked by path; prompts in `memory/`).
  Its LLM profile: see "Hard constraints" above.
  Upstream: `Metta-AI/players` (`players/crewrift/suspectra`). Builds in-lab via
  `tools/build_player.sh suspectra` (same Nim path as notsus).
</content>
