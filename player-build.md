# Building a Coworld player image

What **any** Coworld player image must be, and how to build, test, and ship one. The
image **contract is game-agnostic** — identical for every Coworld; only the *protocol*
your code speaks over the websocket is game-specific. (Verified against coworld
0.1.20 / metta `main`: `packages/coworld/.../docs/roles/PLAYER.md`, `runner/runner.py`.)

## The contract — what the runner requires of your image

A player is a short-lived **linux/amd64** container the runner starts **once per
slot**. It must:

1. **Read `COWORLD_PLAYER_WS_URL`** from the environment — a ready-to-use
   `ws://<game-host>:8080/player?slot=<N>&token=<T>`. (The runner also sets
   `COGAMES_ENGINE_WS_URL` to the *same value* as a legacy alias — **prefer the
   canonical `COWORLD_PLAYER_WS_URL`.**)
2. **Connect to that websocket and speak the game's player protocol**
   (`game.protocols.player` in the manifest) — receive observations, emit actions.
   **This is the one game-specific piece** (e.g. Crewrift's binary Sprite-v1 vs a
   JSON game).
3. **Act only for its own slot** — the runner hands each container its own slot/token;
   never drive another slot.
4. **Exit cleanly when the episode ends.**

Plus, for the image itself:

- **linux/amd64** — hard-checked at run *and* upload; arm64 is rejected. On Apple
  Silicon, build with `docker build --platform linux/amd64 …`.
- **No secrets baked in** — the image is hashed/stored (bundled images are even
  mirrored public). Attach secrets at upload (`--secret-env`, `--use-bedrock`), never
  in the image or manifest env.
- **stdout/stderr are diagnostic logs only** — the source of truth for an episode is
  the game's results/replay, not player logs.
- **Lightweight** — hosted default is **250m CPU / 256Mi memory** per player.

## The minimal Dockerfile

A small base, a websocket client, your code, and a command that runs your player:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir websockets       # + your player's own deps
WORKDIR /app
COPY . /app/your_player
ENV PYTHONPATH=/app
# The command must read COWORLD_PLAYER_WS_URL, connect, play one slot, and exit.
CMD ["python", "-m", "your_player.bridge"]
```

The container's command is **either** this baked `ENTRYPOINT`/`CMD`, **or** the `run`
argv you supply at upload (`--run python --run -m --run your_player.bridge`), which
**overrides** the image's command. `run` is *optional* when the baked command is
correct; pass it to override, or to disambiguate an image that bundles multiple roles.

The bridge itself is roughly:

```python
import asyncio, os, websockets
async def main():
    url = os.environ["COWORLD_PLAYER_WS_URL"]            # the canonical var
    async with websockets.connect(url, max_size=None) as ws:
        async for message in ws:                          # speak the GAME'S protocol here
            ...                                            # (game-specific decode/act/encode)
        # connection closed cleanly ⇒ episode over ⇒ exit 0
asyncio.run(main())
```

## Build → test → ship

1. **Build amd64:**  `docker build --platform linux/amd64 -t <your-tag>:dev .`
2. **Smoke-test locally** (Gate 1 — does it connect → play → exit cleanly?): the
   **`coworld-local-run`** skill.
3. **Upload as a new version** (routine, inert) and — gated — **submit + monitor**: the
   **`coworld-policy-lifecycle`** skill
   (`coworld upload-policy <image> --name <name> [--run …]` →
   `coworld submit <name> --league <id>`).

## Secrets, LLM keys, Bedrock

Never bake keys into the image. Attach them to the **policy version** at upload — they
land only in that version's pod:

```sh
coworld upload-policy <image> --name <name> --run python --run -m --run your_player.bridge \
  --secret-env API_KEY=...                                   # → AWS Secrets Manager
coworld upload-policy <image> --name <name> ... --use-bedrock --bedrock-model us.amazon.nova-micro-v1:0
```

Game-specific model and token-budget rules live in that game's lab guide (Crewrift:
`crewrift_lab/AGENTS.md`, "Hard constraints").

For **local** testing, pass `--secret-env` / `--use-bedrock` to `coworld run-episode`
(the `coworld-local-run` skill) — those values inject only into that run's container.

## What's game-specific (NOT in this guide)

This guide is the agnostic image contract + build/ship flow. The parts that depend on
the game live in **that game's lab**, not here:

- **Speaking the protocol** — decoding observations / encoding actions for the specific
  game (the body of the bridge above).
- **The player's logic** — perception, belief, strategy.
- **That player's actual build** — its real Dockerfile / build script and any
  source-repo build harness.

Full contracts: `docs/roles/PLAYER.md` (player side) and `docs/roles/GAME.md` (the
mirror `/player` route) in the metta coworld package; `COOKBOOK.md` for the upload /
submit / secrets details.
