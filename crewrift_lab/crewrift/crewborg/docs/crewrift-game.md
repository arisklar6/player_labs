> Scope: Crewrift game reference for crewborg, moved word for word from `../AGENTS.md` §2 on 2026-10-30.

## 2. Crewrift (the game)

Crewborg's contract. Two repos matter:

- **Game source (Nim):** the `Metta-AI/coworld-crewrift` repo — the authoritative
  rules, protocol docs, reference bots, map assets. Read this for behavior.
- **Coworld platform docs:** `Metta-AI/metta`: `packages/coworld` *(**read-only**
  reference — never write there)* — the generic Coworld
  packaging/runner/CLI contract Crewrift conforms to.

### Concept & objective (`coworld-crewrift/README.md`, `docs/rules.md`)

Social deduction, 8 players / 2 imposters default, retro pixel art.
- **Crewmates** win by completing all assigned tasks **or** voting out all
  imposters.
- **Imposters** win by killing crew down to parity, or surviving the vote.
- Meetings are triggered by reporting a body or the emergency button; players
  chat then vote (or skip); ties/timeouts eject no one.

### Loop, mechanics, scoring

> **Citation key** (all paths are in the `Metta-AI/coworld-crewrift` repo, verified
> 2026-05-28). Game source: `sim` = `src/crewrift/sim.nim`, `global` =
> `src/crewrift/global.nim` (the `/player` renderer), `server` =
> `src/crewrift/server.nim`, `protocol` = `src/crewrift/common/protocol.nim`.
> Reference consumer: `notsus` = `players/notsus/notsus.nim`, `np` =
> `players/notsus/notsus/protocols.nim`. Cited as e.g. `sim:2464`.

Runs at **24 FPS** (`TargetFps`). Crewmates do timed tasks at stations; imposters
kill (range + cooldown), vent (teleport between grouped vents), and blend in.
Dead players become ghosts (a Crewmate ghost can still finish its own tasks; no
other actions). Phases: `Lobby → RoleReveal → Playing → (Voting → VoteResult)* →
GameOver`. **Inputs only do anything during `Playing` and `Voting`** — all other
phases ignore buttons.

Verified constants and rewards (`sim` const block; defaults, all config-overridable
via `defaultGameConfig` at `sim:1016`):

| Constant | Value | Cite | | Reward | Value | Cite |
| --- | --- | --- | --- | --- | --- | --- |
| `TargetFps` | 24 | `sim:49` | | task complete | +1 | `sim:95`, awarded `sim:2231` |
| `KillRange` | 20 px (dist² ≤ 400) | `sim:56` | | kill | +10 | `sim:96`, `sim:2502` |
| `KillCooldownTicks` | 900 (37.5 s) | `sim:57` | | win (each winner) | +100 | `sim:97` |
| `VentRange` | 16 px (dist² ≤ 256) | `sim:61` | | vote timeout (per non-voter) | −10 | `sim:98`, `sim:3082` |
| `ReportRange` | 20 px | `sim:65` | | stuck (idle crewmate) | −1 | `sim:99` |
| `TaskCompleteTicks` | 72 (3 s hold-A) | `sim:59` | | map size | 1235×659 | `sim:25-26` |
| `VoteTimerTicks` | 240 (10 s) | `sim:72` | | screen/camera | 128×128 | `sim:100-109` |
| `TasksPerPlayer` | 8 | `sim:77` | | | | |
| `ButtonCalls` | 1 per player | `sim:79` | | | | |

Win: crew win if all imposters dead **or** all tasks done; imposters win when alive
imposters ≥ alive crewmates (`checkWinCondition`, `sim:3248`). Imposter count
auto-scales `(players−3)//2` by default. Movement is **momentum-based**
(`Accel=76`, friction `144/256`, `MaxSpeed=704`, sub-pixel `MotionScale=256`;
`sim:42-47`, applied in `applyInput` `sim:2768-2830`) — the action resolver owns
that, not modes. Endpoint path is `/player` (`sim:177`).

### Sprite v1 protocol: structured scene, not a framebuffer (`coworld-crewrift/docs/sprite_v1.md` — READ THIS)

This is the most important thing to get right. **Sprite v1 sends structured
scene data, and Crewrift uses it specifically so agents do *not* need computer
vision.** Don't parse pixels to recover game state — the state is already
structured and labelled in the messages.

Binary WebSocket. The client maintains **three tables** as messages arrive:

| Table | Keyed by | Holds |
| --- | --- | --- |
| **Layers** | `u8` layer id | type (map / one of 8 UI anchors) + flags + viewport size |
| **Sprites** | `u16` sprite id | width, height, **text label**, RGBA pixels |
| **Objects** | `u16` object id | **x, y** (`i16`; *camera-relative* on `/player` — see below), z (draw order), layer, **sprite id** |

**Server → client** messages: define-sprite (`0x01`, id + w/h + snappy RGBA +
label), define-object (`0x02`, id + x/y/z + layer + sprite_id), delete-object
(`0x03`), clear-objects (`0x04`, keeps sprite defs), set-viewport (`0x05`),
define-layer (`0x06`). These are **incremental and stateful** — there is no
"frame" message; you apply each update to the tables and read the tables. Wire
format is in `docs/sprite_v1.md`; a clean reference decoder (the exact byte
layout, little-endian, `i16` coords) is `notsus`' `applySpritePacket` at
`np:408-523`.

The `/player` stream — facts below verified against `global` (the renderer,
`buildSpriteProtocolPlayerUpdates` `global:2276`, init `buildSpriteProtocolPlayerInit`
`global:1720`), `server` (send loop), and the `notsus` parser (`np`):

**Stream shape.** First message is an **init burst**: Clear-objects (`0x04`),
one Define-layer (`0x06`) for **layer 0** (map, type `0x00`), one Set-viewport
(`0x05`) of **128×128**, then Define-sprite (`0x01`) for all *static* sprites
(`map`, `walkability map`, the per-color player/ghost/body sprites, task/HUD
icons) — `global:1720-1855`. After that, **one binary message per game tick**
carrying only changes: Define-object (`0x02`) for everything currently visible
(re-sent each tick) and Delete-object (`0x03`) for anything that left (the
diff-against-last-frame loop, `global:2533`). Init is sent once, gated on
`nextState.initialized` (`global:2289`). **Everything is on layer 0** for
`/player` — no separate UI-anchor layers; HUD/voting elements are objects at
fixed screen coordinates. Treat one received binary message = one atomic frame.

**Coordinates are camera-relative, NOT world space.** This is the single most
important implementation fact and the protocol doc does *not* spell it out for
`/player`. The camera is centered on the local player (`playerView`, `sim:2879`;
camera applied at `global:2323`); an object's `x/y` is `world − camera`, in the
0–128 screen range.
- **You recover the camera from the map object:** the world-map object has
  **object id 1 and sprite id 1** (`MapObjectId`/`MapSpriteId`, `np:14-15`),
  placed at `(−cameraX, −cameraY)` (`global:2331-2333`). So `cameraX =
  −mapObject.x`, `worldX = obj.x + cameraX` — exactly what `notsus` does at
  `np:496-499`.
- **Your own player is *not* an object** — it's the implicit camera center. Your
  world position ≈ `camera + (SpriteDrawOffX + 64 − SpriteSize/2, …)` (the fixed
  center offset, `notsus:22`, applied `notsus:486-492`; `SpriteDrawOffX=2`,
  `SpriteDrawOffY=8` at `sim:38-40`). Read your own *color/role/state* from HUD
  sprites (see labels below), not from a self object.

**Identity by sprite label + object-id range** (no CV). An object references a
sprite; that sprite's **label** tells you what it is. Verified label vocabulary
(all in the `/player` init at `global`):
- Players: `player <color> right` / `player <color> left` (`global:1807,1815`);
  `ghost <color> right`/`left` (`global:1835,1843`); dead bodies `body <color>`
  (`global:1855`). `<color>` ∈ 16 names (`PlayerColorNames`, `global:109-126`):
  `red, orange, yellow, light blue, pink, lime, blue, pale blue, gray, white,
  dark brown, brown, dark teal, green, dark navy, black`.
- World/HUD: `map` (`global:1736`), `walkability map` (`global:1744`),
  `task bubble` (`global:1752`), `task arrow` (off-screen task pointer,
  `global:1784`), `imposter icon` / `imposter icon cooldown` (⇒ *you* are
  imposter, kill ready / cooling, `global:1760,1768`), `ghost icon` (⇒ *you* are
  dead, `global:1776`), `progress bar N%` (`global:2464`), `task counter N`
  (`global:2519`), `shadow` (screen-sized per-player vision overlay, object `13000`
  / sprite `5010`; decoded into a line-of-sight mask — opaque ⇒ occluded,
  transparent ⇒ visible — resent on any camera move, `global:2212`, `sim:2974`).
- Voting: `vote cursor` (`global:1521`), `vote skip cursor` (`global:1529`),
  `vote self marker <color>` (`global:1538`), `vote dot <color>` (tally,
  `global:1546`), `vote timer` (`global:1252`).
- Social UI (meeting/result screens, decoded into chat + census + ejection;
  `global:739-1280`): chat is a text sprite (label = the raw message, id `9000+`)
  paired by screen-y to a speaker icon (`player <color>`, id `9200+`); the voting
  candidate grid (`9300+seq`) shows each player as `player <color>` (alive) or
  `body <color>` (dead) — an authoritative alive/dead census by color; the
  vote-result icon (`9600`, `player <color>`) names the ejected player.
- Phase/result **text** (read game phase from which appear; `interstitialTextItems`,
  `global:957-1044`): `WAITING`/`NEED MORE!` (`global:966-967`), `STARTING`
  (`global:970`), `IMPS`/`CREWMATE` (role reveal, `global:992`), `SKIP`
  (`global:1009`), `NO ONE`/`WAS KILLED` (vote result, `global:1014,1017`),
  `DRAW`/`CREW WINS`/`IMPS WIN` (game over, `global:1021-1025`).
- **Object ids are stable per entity across ticks** (track by id): players
  `1000 + joinOrder` (`spriteObjectId`, `global:1858`), bodies `2000 + i`
  (`spriteBodyObjectId`, `global:2069` — note `i` is the bodies-seq index, **not**
  the dead player's joinOrder, so a body links to its player by **color**, not id),
  task bubbles `3000 + taskIndex` (`spriteTaskObjectId`, `global:2073`), map `1`,
  vote dots `10100 + target*MaxPlayers + voter` (base `notsus:167`, decoded
  `notsus:1827`).

**Vents, rooms, and the emergency button are NOT objects** — they're baked into
the `map` sprite's pixels (`buildMapSpritePixels`, `global:701`). crewborg can't
read their positions from the stream; get them from the static map /
`walkability map` mask or out-of-band map data.

**Walkability** = the alpha channel of the one sprite labeled `walkability map`
(alpha > 0 ⇒ walkable), sized to the full 1235×659 map. Built server-side at
`buildWalkabilitySpritePixels` `global:709`; decoded by `notsus` at `np:389-406`
(alpha-only mask). Snappy-decompress it once; `nav.py` builds the pixel-validated
nav graph over it (design §6). The only other sprite whose pixels crewborg decodes is the
dynamic `shadow` line-of-sight overlay (above); ignore every other sprite's pixels.

**Client → server (input).** Player input is `0x84` + one **byte** bitmask
(`[0x84, mask & 0x7f]`; encoder `np:194`, server masks bit 7 at `global:501`,
decodes via `decodeInputMask` at `server:850`). Bits (`protocol:14-20`):
up/down/left/right = `0x01/0x02/0x04/0x08`, Select `0x10` (unused by the game), A
`0x20`, B `0x40`, bit 7 reserved = 0. **Send only when the held mask changes**;
omitted bits = released. Meeting chat is `0x81` + `u16` len + printable ASCII
(accumulated at `global:485`), accepted **only during Voting** (routed
`server:866` → `addVotingChat` which early-returns off-phase, `sim:2586`). Mouse
(`0x82`/`0x83`) is *not* read by Crewrift's logic — don't rely on it. Verified
game semantics (handler `applyInput`, `sim:2751`):
- **A (`0x20`) is edge-triggered** (`freshA`, `sim:2837`; press→release→press to
  repeat). On a fresh press during `Playing`, in order: try **report** a body in
  range (`sim:2839`, `tryReport` `sim:2614`) → try the **emergency button**
  (`sim:2842`, `tryCallButton` `sim:2634`, ≤1 call/player) → if imposter, try
  **kill** (`sim:2846-2847`, `tryKill` `sim:2464`, nearest crewmate in
  `KillRange`, off cooldown). Report/button open a meeting and short-circuit, so
  you can't kill in the same press that calls one.
- **Task completion = hold A while standing still** inside an assigned,
  incomplete task rect for `TaskCompleteTicks`; any d-pad input resets progress
  (`sim:2866-2877`). Crewmates only.
- **B (`0x40`) = vent**, imposter only, held/level-triggered (`sim:2834`,
  `tryVent` `sim:2506`), gated by `VentRange` + a 30-tick vent cooldown
  (`sim:2547`); teleports to the next vent in the group.
- **Voting** (the `step` Voting branch, `sim:3834-3867`): move a cursor with the
  d-pad (up **or** left = −1, down **or** right = +1; `moveCursor` calls at
  `sim:3851,3853`, proc `sim:3120`), then press **A to confirm** (`sim:3854`).
  The **skip** choice is the last cell (index `== player count` ⇒ vote `−2`,
  `sim:3857`); a player vote stores the cursor index (`sim:3859`). No mouse, no
  text-vote; `0x81` is chat only. A vote is final once cast; not voting before
  the timer ⇒ −10.

So **crewborg's perception is structured-scene maintenance**, not vision: keep
the object/sprite tables current, derive the camera from object 1, resolve each
object to `(label, world-x, world-y)`, and fold that into belief (self
pos/role/state, other players, bodies, task icons, voting state, phase). The only
image steps are two sprite alpha masks: the static `walkability map` and the
dynamic `shadow` line-of-sight overlay. This is dramatically simpler than a
pixel-CV stack — crewborg's perception is **structured-scene maintenance**, not
computer vision; there is no framebuffer parser and no pixel atlas (the only image
steps are Snappy-decoding those two alpha masks).

**Step cadence (a crewborg design choice, grounded in the server).** The server
emits exactly one binary message per socket per 24 Hz tick (one `sim.step` per
loop, send loop, rate-limited by `runFrameLimiter` `server:578`). There is no
"frame complete" sub-message marker, but each WebSocket message is itself one
complete frame: the decoder applies all of its concatenated sub-messages. So the
bridge blocks for one message, applies it, runs one `perceive→…→resolve` cycle,
and sends input *only if the mask changed*. `notsus`' `receiveLatestFrameInto`
(`np:611`) also drains any already-queued messages to act on the freshest frame —
a latency optimization crewborg skips (it has no rate limiter and self-corrects
from transient backlog). Tolerate partial startup frames — don't assume the map
object / walkability sprite have arrived yet on the first ticks.

### Connecting (`coworld-crewrift/README.md`)

Hosted play sets `COWORLD_PLAYER_WS_URL=ws://<svc>:8080/player?slot=<s>&token=<t>`
— connect to it **exactly**; don't hardcode slot/token. Browser clients:
`/client/player`, `/client/global`, `/client/replay`, `/client/admin`. Reference
bots live in `coworld-crewrift/players/` (`notsus`, `evidencebot_v2`,
`nottoodumb`) with guides `how_to_make_a_bot.md`, `SMART_BOT_GUIDE.md`,
`how_to_submit_coworld_policy.md`.

### Runtime contract

Crewborg runs as a **WebSocket client**: the Coworld runner sets
`COWORLD_PLAYER_WS_URL` (legacy alias `COGAMES_ENGINE_WS_URL`), the bridge (`coworld/policy_player.py`) connects, speaks
Crewrift's binary protocol for its slot, and exits on the final message.
**stdout = protocol channel, stderr = logs/traces.** Platform contract:
`coworld/src/coworld/docs/README.md` (overview + role/artifact docs under
`docs/roles/` and `docs/artifacts/`) and `runner/runner.py` (protocol authority).

