# Suspicion model — empirical calibration (2026-08-10)

Measured from **320 hosted Crewrift Prime replays** (≈13.4k player-observations) where the
true roles are known exactly, because the experience requests forced them via
`game_config_overrides.slots`. Scripts: see the session that produced `watts:v1`/`v2`
(`analyze.py`, `calibrate.py`, `accuse.py` — replay-only, since hosted `results.json` and
policy logs are 403 for external accounts, cf.
[coworld#37](https://github.com/Metta-AI/coworld/issues/37)).

Roles were forced per batch, so "is this player an imposter" is ground truth rather than
inferred. Room-level co-location is used as the observable proxy for crewborg's
pixel-level tests — it is **coarser**, so the measured LRs below are conservative
(a tighter proximity test could score higher).

## 1. The hand-picked evidence weights are overstated

| Clue (`strategy/suspicion.py`) | Assumed | Measured LR | P(clue \| imp) | P(clue \| crew) | n |
| --- | --- | --- | --- | --- | --- |
| `BODY_NEAR_LOG_LR` = log(3.0) | 3.00 | **1.36** | 0.439 | 0.323 | 2 486 |
| `FOLLOW_LOG_LR` = log(6.0) | 6.00 | **2.51** | 0.439 | 0.175 | 5 435 |
| (co-present at the kill tick) | — | 3.24 | 0.541 | 0.167 | 5 435 |

Both weights overstate their evidence by a consistent **≈2.2–2.4×**.

## 2. The posterior is well-calibrated at the top and broken in the middle

Independent of the proxy above — measured from crewborg's *own* votes, since it only votes
when the posterior clears the bar, making accuracy a direct calibration test:

| Band | Model claims | Actually right | Verdict |
| --- | --- | --- | --- |
| ≥ 0.80 | ≥ 80% | **30/37 = 81%** | well calibrated |
| 0.65–0.80 | 65–80% | **≈1/31 ≈ 3%** | catastrophic (random = 29%) |

**Why:** the ≥0.80 votes are dominated by `WITNESSED_LOG_LR = log(1e6)` — actually seeing a
kill or a vent, which is effectively ground truth. The 0.65–0.80 band is pure
circumstantial stacking of the two overstated weights above. This is what killed
`watts:v2` (bar 0.8 → 0.65): named votes rose 9 → 40 but accuracy fell 56% → 20%, and
innocent ejections went 4 → 32 per 60 episodes.

**Consequence, and it is counterintuitive:** correcting the weights *downward* makes
crewborg vote **less**, not better. Its circumstantial evidence genuinely cannot identify
imposters; only witnessing can, and witnessing is rare (~0.15 qualifying votes/episode).
Fixing the weights is a correctness fix, not a win-rate fix.

## 3. The ignored signal: other players' accusations

`_recompute()` combines prior + `WITNESSED` + `_graded_log_lr` (vent + body + follow).
There is **no term for what other players say**, yet the field broadcasts explicit
"vote &lt;colour&gt;" calls every meeting:

| Evidence | Precision | LR vs prior (2/7) | n |
| --- | --- | --- | --- |
| Other players' *votes* | 32.6% | 1.21 | 1 900 |
| Chat accusation, **1** distinct accuser | 54.9% | **3.04** | 576 |
| Chat accusation, **2** distinct accusers | 86.8% | **16.50** | 38 |
| Chat accusation, **3+** distinct accusers | 100% | ∞ | 5 |

Following the crowd's *votes* is worthless (32.6% vs a 28.6% baseline). But a **spoken
accusation is worth LR ≈ 3.0 on its own — as much as crewborg wrongly credits
body-proximity — and two independent accusers is LR ≈ 16.5**, which clears the 0.8 vote
bar unaided (prior odds 0.4 × 16.5 = 6.6 → p = 0.87).

### Proposed change (not yet implemented)

Add an accusation term to `_graded_log_lr`, weighted from the table above rather than
guessed, keeping `VOTE_PROBABILITY = 0.8`:

- 1 distinct accuser → log(3.0) — deliberately *not* enough to vote alone (55% precision)
- 2 distinct accusers → log(16.5) — clears the bar
- 3+ → capped (n = 5, don't over-fit)

Expected effect: qualifying votes roughly double (≈0.15 → ≈0.36/episode) while precision
stays high (~81% → ~85%). **Risk to watch:** this is manipulable — two imposters who both
accuse the same crewmate would trigger a wrong ejection. Empirically that isn't happening
in the current field (86.8% precision at 2 accusers), but it is an adaptive exploit, so
re-measure precision whenever the field shifts.
