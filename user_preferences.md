# User preferences

Durable preferences the human has expressed for working in this lab — how to
communicate, what to do or avoid, defaults to assume. `AGENTS.md` tells you to
**read this on startup**.

When the human states a preference (explicitly, or clearly through repeated
correction), **record it here** as a short, concrete entry so it persists across
sessions. Keep it tidy: one bullet per preference, drop ones that are superseded.

## Preferences

- **One policy name per bot; increment only the version tag.** Always upload as
  `coworld upload-policy <image> --name <stable-name>` and let the server auto-increment
  `vN` — `my-bot:v1`, `my-bot:v2`, `my-bot:v3`. **Never** mint a new *name* per attempt
  (`my-bot-v1`, `my-bot-v2` as separate policies).
  **Why:** the Progress / counterfactual-evals dashboard only generates a check when a new
  version is uploaded under a policy name that has *already played in a league* — it
  replays that league's frozen episodes with just the new version swapped in. A unique
  name per attempt reads as an unrelated policy with no version history, so no comparison
  ever runs and nothing shows on the Progress page.
  Applies across **every** coworld/league (Proxy War, Heartleaf, Zero Sum, Crewrift Prime,
  Paintbot, Jumper, …), not just Crewrift. Verify a chain with
  `policy_lifecycle.py versions --name <name>`: one policy, many versions.
</content>
