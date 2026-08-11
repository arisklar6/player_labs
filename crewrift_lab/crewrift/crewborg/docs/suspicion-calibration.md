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

---

## 4. Controlled re-test in the `crewrift-prime-vote-basic` drill

Both hypotheses were re-tested in Prime's voting drill (1 forced imposter among 8, 3000
ticks, 2 tasks/player, a guaranteed button call), 90 episodes per arm, 270 total, 0
failures, all three arms fired back-to-back against the same field. Target composed as
`target: {division_id, variant_id: "crewrift-prime-vote-basic"}` — note `top_n` rosters
**require** a league/division target, so a bare `coworld_id` target 400s.

| Arm | Crew win | Imposter ejected | Named votes | Vote accuracy | watts voted out |
| --- | --- | --- | --- | --- | --- |
| v1 (bar 0.8) | 96.7% | 5.6% | 15 / 235 | 46.7% | **0** |
| v2 (bar 0.65) | 97.8% | 13.3% (p=0.12) | 111 / 224 (p=6e-27) | 31.5% (p=0.26) | **8** (p=0.007) |
| v3 (accusation cue) | 97.8% | 11.1% (p=0.28) | 13 / 202 (p=1.0) | 76.9% (p=0.14) | **0** |

Random baseline for a named vote here is **14.3%** (1 imposter among 7 others), not the
28.6% of league play.

**The drill has a ceiling on its headline metric.** Crew win 96.7–97.8% in every arm —
with only 2 tasks/player the crew finish before the lone imposter matters. Use *imposter
ejected* and *vote accuracy*, never win rate, as the target axis here.

**H1 (lower the bar) — still rejected, and now with a mechanism.** It fires decisively
and does eject the imposter more than twice as often (not significant at n=90). But it
gets **watts itself voted out 8 times vs never** (p=0.007) — voting on weak reads makes
you the suspect. That is a plausible mechanism for the league regression, not just lost
precision.

**H2 (accusation cue) — confirmed inert, and its apparent win was an artifact.**
Splitting v3's 13 named votes by whether the meeting actually contained an accusation:

| | votes | correct |
| --- | --- | --- |
| meetings **with** an accusation (cue *can* fire) | 6 | 3 (50%) |
| meetings with **no** accusation (cue provably cannot fire) | 7 | **7 (100%)** |

The entire accuracy gain sits in meetings where `_accusation_log_lr` returns 0.0 and v3
is **byte-identical in behaviour to v1**. Same code, 7/7 versus v1's 4/10 — a crisp
measurement of how much noise lives in a 10-vote sample. The cue did nothing.

Only 5–9% of drill meetings contained any accusation (vs 71% in the batches the weights
were fitted on), so the cue remains untested rather than disproven.

**New lead — the model may degrade with multiple imposters.** v2's votes were
*informative* in the drill (31.5% vs a 14.3% baseline = 2.2×) but *anti-informative* in
league play (20% vs 28.6% = 0.7×). The clearest structural difference is 1 imposter vs 2:
with two killers, "who was co-located with the victim" stops identifying a unique
suspect. Confounded by config and field differences, so this is a hypothesis — but it is
testable directly by overriding `imposterCount`, and it would mean the drill is
systematically easier than the league on exactly the axis we care about.
