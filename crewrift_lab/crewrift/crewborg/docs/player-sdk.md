> Scope: Player SDK reference for crewborg, moved word for word from `../AGENTS.md` §1 on 2026-10-30.

## 1. The Player SDK (`players.player_sdk`)

**Source:** the public `Metta-AI/players` repo (`players/player_sdk`), installed into
the lab from `main` (lock-pinned) via `pyproject.toml` — no local checkout; the SDK is
imported, not vendored in this fork.
**Import root:** `players.player_sdk` (the repo is the `players` package).
Pure Python, deps `numpy`/`pydantic`/`websockets`.

### The two-loop model

```
perceive ──► update_belief ──► mode.decide ──► resolve_action ──► wire command
   ▲                                                                   (per tick)
   │   reflexes (priority-ordered, urgent overrides)
   │
   └── strategy loop (slower):  BeliefSnapshot ──► validated ModeDirective
```

The **inner loop never blocks on strategy**. If no fresh directive is ready, the
runtime applies a configured **default directive**. Directives carry a **TTL**;
on expiry the runtime falls back to default. This keeps the agent live even when
the strategy (e.g. an LLM call) is slow or stalls.

### What you import (verified from `player_sdk/__init__.py`)

```python
from players.player_sdk import (
    AgentRuntime,                 # per-tick inner-loop orchestrator (runtime.py)
    Mode, ModeRegistry,           # deterministic local policies + validation (modes.py)
    ModeDirective, ModeParams, EmptyModeParams, ModeDecision,  # directive types (types.py)
    ActionIntent, ActionCommand,  # symbolic intent / concrete command (types.py)
    SharedMemory, SharedMemoryView, BeliefSnapshot, StrategyResult,  # (types.py)
    Strategy, AsyncStrategy, StrategyRunner,                    # strategy protocols (strategy.py)
    SynchronousStrategyRunner, ThreadedStrategyRunner,
    AsyncStrategyRunner, ManualStrategyRunner,                  # concrete runners
    Reflex, ReflexRule, RuntimeContext,                         # reflexes (runtime.py)
    DirectiveValidationError,                                   # (modes.py)
    OverwriteBuffer,                                            # latest-wins buffer (buffers.py)
    # tracing/metrics (trace.py):
    TraceSink, MetricsSink, TraceEvent, MetricSample,
    ListTraceSink, ListMetricsSink, LoggingTraceSink, LoggingMetricsSink,
    NullTraceSink, NullMetricsSink, WandbMetricsSink,
)
```

The SDK is **generic over six type parameters**: `AgentRuntime[Observation,
Percept, Belief, ActionState, Intent, Command]`. You define all six for
Crewrift.

### What you implement (the game supplies three functions + modes + strategy)

1. **Types** — `Observation` (the current Sprite-v1 scene state: the object /
   sprite / layer tables), `Percept` (parsed tick view: resolved entities with
   labels + coordinates), `Belief` (persistent world model), `ActionState`
   (transport-side mechanics: pending chat, button pulses, movement plan),
   `Intent` (symbolic, e.g. `noop`/`input`/`chat`), `Command` (concrete wire
   packets).
2. **`perceive(observation, tick) -> percept`** — interpret the scene: join each
   object to its sprite's **label** and read the object's **x/y** directly.
   Keep raw sprite pixels *out* of belief.
3. **`update_belief(belief, percept) -> None`** — fold the percept into belief.
   Belief is the **only** interface the strategy sees.
4. **`resolve_action(intent, belief, action_state) -> command`** — translate a
   symbolic intent into wire packets. *All* transport mechanics live here
   (button-bitmask encoding, chat buffering, movement/pathing timing).
5. **`Mode` subclasses** — deterministic local policies, each with a typed
   `params_type` and a `decide(belief, action_state) -> Intent | ModeDecision`.
   Register them in a `ModeRegistry`.
6. **`Strategy`** — reads a `BeliefSnapshot` and returns a validated
   `ModeDirective` (which mode + typed params + TTL). Run it via a
   `*StrategyRunner`.

### Assembly pattern (mirror this exactly)

The SDK's `docs/metta_cogames_framework/examples/toy_grid_agent.py` shows the
canonical `build_runtime()`:

```python
registry = ModeRegistry()
registry.register(IdleMode)
return AgentRuntime(
    belief=Belief(), action_state=ActionState(),
    perceive=perceive, update_belief=update_belief, resolve_action=resolve_action,
    mode_registry=registry,
    default_directive=ModeDirective(mode="idle", source="default", reason="..."),
    strategy_runner=SynchronousStrategyRunner(RuleBasedStrategy()),
    trace_sink=trace_sink, metrics_sink=metrics_sink,
)
```
Then each tick: `command = runtime.step(observation)`; send `command`'s packets.

### Design rules (from `PYTHON_FRAMEWORK.md` — enforce these)

- Raw observations (and sprite pixels) stay out of belief; belief is the
  strategy interface.
- Mode params are typed (`ModeParams`); modes emit **symbolic intents**, never
  transport actions.
- Movement, cursor/button timing, chat buffers, UI mechanics → **action
  resolver**, not modes.
- Keep `snapshot.read()/write()` scopes short; **never hold the lock across an
  LLM/network call**.
- Use reflexes for urgent events that can't wait for the strategy loop.
- Use TTLs + default directives so the agent stays live when strategy stalls.
- Return `ModeDecision.complete(...)` / `.stalled(...)` when a mode finishes or
  is stuck.
- Validate directives in `ModeRegistry` before installing.
- Trace every boundary; emit metrics while developing.

### SDK files

| File | What |
| --- | --- |
| `player_sdk/runtime.py` | `AgentRuntime`, reflexes, fallbacks, the `step()` loop |
| `player_sdk/modes.py` | `Mode`, `ModeRegistry`, directive validation |
| `player_sdk/types.py` | directives, intents, commands, `SharedMemory`/`BeliefSnapshot` |
| `player_sdk/strategy.py` | `Strategy`/`AsyncStrategy` protocols + 4 runners |
| `player_sdk/trace.py` | trace & metrics sinks |
| `player_sdk/buffers.py` | `OverwriteBuffer` (latest-wins, thread-safe) |
| `player_sdk/coworld_json_bridge.py` | JSON-protocol bridge — **NOT for Crewrift** (see below) |
| `player_sdk/docs/metta_cogames_framework/README.md` | full framework reference + invariants/anti-patterns |
| `player_sdk/docs/metta_cogames_framework/PYTHON_FRAMEWORK.md` | quickstart + minimal agent |
| `player_sdk/docs/metta_cogames_framework/examples/toy_grid_agent.py` | complete runnable example — the assembly pattern to mirror |

### Transport: the part the SDK does *not* do for you

`coworld_json_bridge.py` speaks the **JSON `coworld.player.v1`** protocol —
observations are `(location, feature_id, value)` token triplets, the action is a
single `action_name` string, and it hosts a **mettagrid `MultiAgentPolicy`**.
That is for *grid/token* games (cogsguard-style), **not** for a pixel game.

Crewrift speaks **binary Sprite v1** (structured scene updates in, button/text
packets out — see [§2](crewrift-game.md#sprite-v1-protocol-structured-scene-not-a-framebuffer)).
So crewborg must **write its own websocket bridge** that:
1. reads `COWORLD_PLAYER_WS_URL` (the runner fills in `?slot=N&token=...`);
2. `websockets.connect(url, max_size=None)` — token validation is at HTTP
   upgrade, no app handshake;
3. decodes each incoming binary message and applies it to the **scene tables**
   (Layers / Sprites / Objects — see [§2](crewrift-game.md#sprite-v1-protocol-structured-scene-not-a-framebuffer)),
   then on each tick drives `runtime.step(scene)` and sends the resulting wire
   packets (a button packet, optionally a chat packet);
4. exits cleanly when the server closes the socket (= game end).

Each incoming binary message is a complete frame (the decoder applies all of its
concatenated sub-messages), so the bridge applies one message, runs one
`perceive→…→resolve` cycle, and sends input only if the mask changed. `notsus`'
`receiveLatestFrameInto` (`np:611`) additionally drains any already-queued
messages and acts only on the freshest — a latency optimization (skip stale
intermediate frames) that crewborg does not currently need, since it has no rate
limiter and self-corrects from any transient backlog.

