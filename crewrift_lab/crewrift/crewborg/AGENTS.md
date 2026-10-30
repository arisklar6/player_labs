> Scope: orientation and rules for working on the crewborg player (crewrift_lab/crewrift/crewborg). Lab-wide rules: `../../../AGENTS.md`; Crewrift lab rules: `../../AGENTS.md`.

# Crewborg — Agent Notes

**Crewborg** is a Player-SDK–based agent that plays the Coworld game
**Crewrift**. This file is the orientation doc: what the relevant codebases are,
how they fit together, the API/protocol crewborg must satisfy, and pointers to
source for detail. The durable design decisions live in [`design.md`](./design.md).

Everything below was read from source on **2026-05-28**. These repos are in
active development; **verify any specific symbol, path, or constant against the
cited file before relying on it.**

> **Status:** Implemented end-to-end — the agent plays both roles (crewmate
> tasks / meetings / voting / report / flee, plus imposter Evade / Pretend / Search / Hunt and the
> `kill`/`vent` intents; the imposter **evades after fresh kills** and may report
> non-fresh visible bodies;
> imposter Pretend fakes real task stations in likely occupied rooms, Search owns
> pre-kill target acquisition, and
> Hunt is gated on a visible kill opportunity). Attend Meeting has an opt-in
> LLM chat/vote path with deterministic fallback. `CREWBORG_BE_DUMB=1` is an
> aggressive imposter experiment that skips Pretend/Evade/body reports and keeps
> the imposter in Search/Hunt. See [`README.md`](./README.md) for a capability summary and
> [`design.md`](./design.md) for the settled architecture. crewborg is the package
> `crewrift.crewborg`, vendored in the lab at `crewrift_lab/crewrift/crewborg/`.

## Hard constraints

- **Mandatory LLM profile:** Crewrift policies use the model and token budget in [`crewrift_lab/AGENTS.md`](../../AGENTS.md) ("Hard constraints"); it applies to crewborg.

---

## The big picture

Three layers. Crewborg is the top; it treats the protocol below as a contract.

```
  crewborg (this dir)              the agent we are building
        │ builds an AgentRuntime, feeds it scene state, sends back input packets
        ▼
  Player SDK  (players.player_sdk) generic two-loop "Cyborg" agent framework
        │ binary Sprite-v1 WebSocket  (crewborg writes this bridge itself)
        ▼
  Crewrift game server (Nim)       authoritative game; defines the rules
```

- **Crewrift** is an *Among Us–style social-deduction game* (crewmates do tasks
  & vote; imposters kill, vent, and blend in). It is **not** cooperative
  survival. Implemented in **Nim**; it speaks the **binary Sprite v1** wire
  protocol. Crucially, Sprite v1 is a **structured scene protocol, not a
  framebuffer**: the server streams object placements with **exact world
  coordinates** plus sprites that carry **text labels**, *specifically so agents
  read game state from structured data and labels — no computer vision*
  (see [§2 Sprite v1](docs/crewrift-game.md#sprite-v1-protocol-structured-scene-not-a-framebuffer)).
  It is uploaded to Softmax/Observatory as a **Coworld** (a packaged,
  league-runnable game).
- **The Player SDK** (`players.player_sdk`) is a generic Python framework for
  building agents with a *fast symbolic inner loop* + a *slower strategy loop*
  (the architecture is historically called "Cyborg" in the SDK docs). It is
  transport- and game-agnostic.
- **Crewborg** plugs Crewrift-specific perception/belief/modes/strategy into the
  SDK's runtime, and ships as a Docker image the Coworld runner launches.

**Key consequence:** the SDK gives you the *loop and the scaffolding*
(`AgentRuntime`, `Mode`, `ModeDirective`, strategy runners, tracing). You supply
*everything game-specific*: maintain Crewrift's scene state (objects + their
labels and coordinates) as belief, decide modes, and resolve intents into
Sprite-v1 button/text packets. Crewborg also owns its **own websocket bridge** —
the SDK's JSON bridge does not fit a binary game (see
[Transport](docs/player-sdk.md#transport-the-part-the-sdk-does-not-do-for-you)).

---

## 1. The Player SDK (`players.player_sdk`)

Moved word for word to [`docs/player-sdk.md`](docs/player-sdk.md) (two-loop model, imports, what you implement, assembly pattern, design rules, SDK files, transport). Read it before writing player code.

---

## 2. Crewrift (the game)

Moved word for word to [`docs/crewrift-game.md`](docs/crewrift-game.md) (concept, mechanics and scoring, the Sprite v1 scene protocol, connecting, runtime contract). Read its Sprite v1 section before touching perception.

---

## 3. Layout and references

The durable architecture and the full set of design decisions live in
[`design.md`](./design.md) — read it before writing code. It owns the package
layout (`__init__.py`/`types.py`/`action.py`/`nav.py`/`modes/`/`strategy/`/
`perception/`/`map/`/`coworld/`/`tests/`), the type contracts, and the
mode/intent/strategy design. The meeting LLM implementation lives under
`strategy/meeting/` and is enabled only by `CREWBORG_LLM_MEETINGS=1` plus
`ANTHROPIC_API_KEY`.

Perception is **structured-scene maintenance**, not computer vision: there is no
framebuffer parser, no pixel atlas, and no CV parity oracle. The only image steps
are Snappy-decoding two sprite alpha masks: the `walkability map` (used only to
*validate* a baked map — vent/button/task locations are not in the stream) and the
dynamic `shadow` line-of-sight overlay (real per-point visibility); see
[§2](docs/crewrift-game.md#sprite-v1-protocol-structured-scene-not-a-framebuffer) and `design.md` §3.

Behavior & parsing references:
- **Crewrift's `notsus` / `evidencebot_v2` Nim bots** are the behavior references;
  `notsus`' Sprite-v1 *parsing* code (`players/notsus/notsus/protocols.nim`) — how
  it maintains the scene tables, recovers the camera, and interprets labels — is
  the perception reference (label path only; ignore its legacy pixel-CV path).
- **`players/cogsguard/{baseline,buggy,cranky}`** — JSON/`coworld_json_bridge`
  players (token-grid game). **Not** crewborg's transport, but a reference for the
  SDK's JSON bridge.

---

## 4. Tests

This fork is the editable package `crewrift.crewborg`; its tests live under
`crewrift_lab/crewrift/crewborg/tests` and cover the action resolver, modes, trace
sinks, the assembled runtime, an in-process bridge smoke, and the scene decoder
(decode recorded Sprite-v1 sequences → assert resolved objects/labels/coordinates,
rather than pixel parity). Develop/run/test workflows live in the
[lab README](../../README.md).

---

## Quick file index

| Need | Path |
| --- | --- |
| SDK runtime / `step()` | `players/player_sdk/runtime.py` |
| SDK mode base + registry | `players/player_sdk/modes.py` |
| SDK directive/intent/command/belief types | `players/player_sdk/types.py` |
| SDK strategy runners | `players/player_sdk/strategy.py` |
| SDK framework reference (invariants) | `players/player_sdk/docs/metta_cogames_framework/README.md` |
| SDK minimal example to mirror | `players/player_sdk/docs/metta_cogames_framework/examples/toy_grid_agent.py` |
| Crewborg design decisions | `./design.md` (this fork) |
| Crewborg trace-log format + `jq` recipes | [`./docs/trace-logs.md`](./docs/trace-logs.md) |
| Crewrift Sprite-v1 parser (perception reference) | `Metta-AI/coworld-crewrift`: `players/notsus/notsus/protocols.nim` |
| Crewrift rules / mechanics | `Metta-AI/coworld-crewrift`: `README.md`, `docs/rules.md`, `src/crewrift/sim.nim` |
| Crewrift wire protocol | `Metta-AI/coworld-crewrift`: `docs/sprite_v1.md` |
| Crewrift reference bots + guides | `Metta-AI/coworld-crewrift`: `players/` |
| Coworld platform/runner contract | `Metta-AI/metta`: `packages/coworld/src/coworld/docs/README.md` + `runner/runner.py` *(read-only)* |
| Crewborg trace replay viewer | `./viewer/index.html` |

Repo roots:
- Player SDK: pkg `players`, installed from the public `Metta-AI/players` repo (tracks `main`, lock-pinned) (no local checkout)
- This crewborg fork: `crewrift_lab/crewrift/crewborg` in this repo (pkg `crewrift.crewborg`)
- Crewrift game source: the `Metta-AI/coworld-crewrift` repo
- Coworld platform: `Metta-AI/metta`: `packages/coworld` *(read-only reference)*

## Source-of-truth & caveats

The protocol/mechanics in §2 were read from `coworld-crewrift` source on
2026-05-28 (`global.nim`/`server.nim` for the `/player` render, `sim.nim` for
mechanics/constants, `players/notsus/notsus/{protocols,votereader}.nim` for the
proven consumer). Crewrift is in active development, so when something doesn't
match, re-derive from those files (and a live `coworld-crewrift` capture) — they
win over this doc. Specifics worth re-confirming against the live game:

- The **label strings** and **object-id bases** are the perception contract and
  are game-defined (not in `sprite_v1.md`). They're current as of the date above;
  re-check `global.nim` if perception misbehaves.
- `notsus` is a **dual-path** bot: a legacy pixel-CV path *and* the label path.
  Over Sprite v1 the **label path is authoritative** (`spriteDetectionsReady`);
  mirror that and **ignore** its CV/OCR/patch-hash machinery (`votereader.nim`,
  `scoreCamera`, crewmate sprite matching) — it's for the older bitstream wire.
- Constants in the §2 table are defaults; a league variant may override them via
  game config. Read the actual episode config when it matters.
