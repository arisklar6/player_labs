> Scope: lab-wide, game-agnostic rules for player_labs (read on startup; game labs add their own AGENTS.md).

# player_labs — agent guide

An experimentation/optimization lab for Coworld players. This file orients agents
working in the repo. Read it, plus [`best_practices.md`](best_practices.md) and
[`user_preferences.md`](user_preferences.md), on startup.

## Hard constraints

**The two gates.** Gate 1 (yours, every iteration) is just *smoke + correctness* — did
the change take, is it still not crashing; **never a comparative test.** Uploading a
new version is routine and ungated (it's how you get a testable artifact for
experience requests). Gate 2 (the human's, rare) is **league submission** — public,
and likely to become the champion as soon as it qualifies, so hard to roll back. You
avoid rollback by **uploading freely but not submitting** until the player is better
and the human approves.

**Propose-and-pause (do not violate).** When a thread of work finishes, **propose the
next step and pause** — don't auto-chain into unrequested work, especially
strategy/gameplay changes. "Let's do X" means *we* do X with the human in the loop;
when a task is fenced as operations-only, don't drift into behavior changes.

## What this repo is — the improvement loop

player_labs exists to run **one loop**: a human and you (the coding agent)
collaborate to make a competitive Coworld **player** better —
**evaluate its performance via experimentation → diagnose where it falls short →
make a focused improvement → repeat.** That loop is the purpose of everything here.

**Your role.** The human originates the strategic jumps and judges gameplay quality;
**you implement them, build the observability that reveals where a jump is possible,
measure rigorously, and hold the correctness gate.** Your highest-leverage work is
making the human's strategic judgment cheap and well-informed — clear options,
visible behavior, trustworthy numbers — not replacing his decisions. Design for
autonomy by widening what you do *between* his decisions.

**The cycle** — it *starts* with evaluation: you bring the signal, the human sets
direction.

1. **Evaluate** (you) — run experiments via **experience requests**
   (`coworld-experience-requests` skill) against the current uploaded version and
   measure how it performs. Experience requests are the **primary** eval instrument:
   they run many episodes in parallel on Softmax infra, are currently free, and are
   **not scarce** — use them liberally, but **target them to the question** (matched
   roles when the last change was role-specific; the specific opponents the policy
   struggles against). Turn on heavy tracing for the policy if it has it.
2. **Report** (you → human) — pull the replays / logs / results those experiments
   produced (`coworld-episode-artifacts` skill), **extract dense signal** (with that
   skill plus the game's own analysis tools), and
   present it to the human, with recommendations. Targeted when he's chasing a
   specific flaw or investigating a new direction/strategy.
3. **Direction** (human-led) — **consult until the human gives a direction** (a
   behavioral theory or a new capability). Surface decision-ready forks; don't
   pre-decide. Agree the model before writing code for anything non-trivial.
4. **Implement** (you) — change **one** component so the next evaluation is
   attributable; keep tunable knobs in a config layer separate from logic.
5. **Gate 1 — smoke test, then rebuild + re-upload** (you): confirm the change
   **took** and the player still runs without crashing — a **non-comparative** local
   check (`coworld-local-run` skill; you can't run other users' policies locally, so
   this is correctness, not a matchup). Then **rebuild and upload it as a new version**
   (`coworld-policy-lifecycle` skill; the game-agnostic image contract is in
   [`player-build.md`](player-build.md)) — but **do NOT submit it to a league yet.**
   Record the version → change mapping in the version log.
6. **Repeat** — evaluate the new version (back to step 1) and iterate until it is
   **demonstrably better than before.**
7. **Gate 2 — submission permission** (the human's) — only once the player is clearly
   better, **ask the human for permission to submit.**
8. **Submit + monitor** (you, gated) — submit to the league and monitor standings
   (`coworld-policy-lifecycle` skill).

On Ari's machine, agents also follow the shared Coworld rules in `~/.claude/CLAUDE.md`
(section "Coworld player repos"); this file and `best_practices.md` stay the lab's own process.

## Best practices

[`best_practices.md`](best_practices.md) is a small, battle-tested, game-agnostic set
of practices for this loop (measurement rigor, diagnosis discipline, hypothesis
discipline, provenance). **Read it**, treat it as your defaults, and **warn the human
if a request would contravene one** before proceeding.

## User preferences

[`user_preferences.md`](user_preferences.md) records the human's durable preferences
for working here. **Read it on startup**, and when the human states a preference,
**record it there** so it persists across sessions.

## Skills

Lab-wide, game-agnostic Coworld tooling lives in `.claude/skills/`:

- **`coworld-experience-requests`** — create and monitor hosted *experience
  requests* (batches of episodes you define: target, roster, roles, count) for
  evaluating agents against a live roster. (Loop step 1: **Evaluate**.)
  `references/api.md` is the full request-API field reference;
  `scripts/experience_request.py` does `resolve` / `create` / `monitor`.
- **`coworld-episode-artifacts`** — download completed episodes' replays, results,
  and per-agent logs into one directory per episode (keyed off `job_id`). (Loop step
  2: **Report**, the pull.)
- **`coworld-local-run`** — run your own built policy in a **local** episode and watch
  it; the Gate-1 smoke test (did the change take, does it connect→play→exit cleanly —
  *not* a comparative matchup). `scripts/smoke.py`. (Loop step 5.)
- **`coworld-policy-lifecycle`** — **upload** a built image as a new version → (gated)
  **submit** to a league → **monitor** standings, with version-log discipline. Upload
  is routine/inert; submit is the irreversible champion-making action.
  `scripts/policy_lifecycle.py` does `versions` / `monitor`. (Loop steps 5–8.)

These cover the lab-wide, mechanical halves of the loop. **Game-specific skills/tools
— result analysis (scoring/roles), the player's build, its observability — belong
under that game's lab directory, not here.**

## Deferred tasks

Tasks we've intentionally parked for later live in [`TODO.md`](TODO.md) (Open/Done
structure). **Check it at the start of focused work, and add to it whenever you
defer something mid-session** (note what, and any context the future task needs).

## Keep the root game/world-agnostic

Everything at the **project root** — code, docs, markdown, and the lab-wide skills
in `.claude/skills/` — must be **game/world agnostic**: it should serve any Coworld,
not one specific game. Anything tied to a single game/world (a player and its tests,
that game's rules/mechanics, its result analysis) lives under that game's lab
directory (e.g. `crewrift_lab/`), never at the root.
