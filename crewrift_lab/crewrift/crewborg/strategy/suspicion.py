"""Bayesian suspicion: posterior P(imposter) per player (design §10.1).

→ Canonical reference: ``docs/designs/suspicion.md`` — the living home for the
model, each evidence type's log-LR function (form + parameters + shape), the offline
fitting workflow, and the provenance log. Update that doc whenever a function or its
constants change.

Crewmate POV. For every other player we maintain `belief.suspicion[color]` = the
posterior **probability they are an imposter**, updated from a combinatorial prior
by the evidence we have observed. The score is a real probability, so thresholds
(e.g. the flee bar) are interpretable — no magic numbers.

**Prior.** With `P` players and `K` imposters, a crewmate knows the `K` imposters
are among the other `P − 1`; by symmetry each other player's marginal prior is
`K / (P − 1)`. `K` is derived from the player count via the game's auto formula
(`(P − 3) // 2`), overridable by `belief.imposter_count`.

**Update.** Work in log-odds: `logit(P) = logit(prior) + Σ_e logLR(e)` over observed
evidence `e`. `P = sigmoid(logit)`. The log-LR of each graded cue is a simple,
hand-written **function of the event's features** (`_*_log_lr` below), not a flat
constant — because the relationship isn't flat (a skilled imposter flees rather than
dwelling). The function forms and their constants are the **parameterization** (and
the learnable surface — there is no learning machinery yet).

**Evidence**, by type, contributes its most-suspicious instance (we aggregate with
`max` per type), so an unbounded event log can't inflate the posterior and there's
no double-counting; and because role is a fixed latent, evidence **persists** (no
time decay):

- Near-certain (`WITNESSED_LOG_LR` ⇒ P ≈ 1), from frame-to-frame transitions on the
  tape (§5.1): *witnessed kill* (lone kill-range neighbour of a just-killed victim)
  and *witnessed vent* (emergence / submersion, line-of-sight via the `shadow` mask).
- Graded functions over the event log (§5.2): **vent dwell** (weak, ~flat past a
  pass-through), **body proximity** (log-LR *decreases* with dwell — brief is the
  only window on a fleeing killer), **follow-to-death** (log-LR *increases* with how
  long the shadowing lasted).

`believed_imposters` (which gates Flee) is every alive player with `P ≥
FLEE_PROBABILITY`. Crewmate-only — an imposter knows the truth, a ghost doesn't flee.

v1 simplifications (documented for later): naive-Bayes independence between evidence
types; positive-evidence-only (the prior is the baseline — no exculpatory terms);
and a static `K / (P − 1)` prior without redistributing the imposter budget as
players are confirmed/die (a proper joint model is a refinement).
"""

from __future__ import annotations

import math
import re

from crewrift.crewborg.action import KILL_RANGE_SQ
from crewrift.crewborg.strategy.occupancy import (
    neighbors_within,
    players_in_rect,
    rect_visible,
)
from crewrift.crewborg.types import Belief, PerceptionFrame, PlayerEvent, PlayerRecord

# Each evidence type contributes a log-likelihood-ratio, log(P(e|imp)/P(e|crew)), to
# the posterior. Witnessed kill/vent are definitional near-certainties (a constant).
# The graded event-log cues use simple, hand-written **per-event functions** of the
# event's features (duration, distance) — `_*_log_lr` below — because the
# relationship is not flat: a skilled imposter *flees* rather than dwelling, so e.g.
# body-proximity is MORE suspicious when brief. The function form + its constants ARE
# the parameterization (no learning machinery yet); docs/designs/suspicion.md §3
# documents each shape and §6 how to (re)fit the constants from replays. Keep code
# and doc in sync, and log changes in the provenance table (§7).

# Near-certain catches (we saw it happen): an overwhelming log-LR ⇒ P ≈ 1.
WITNESSED_LOG_LR = math.log(1e6)

# vent dwell — weak: a real venter teleports (caught by the transition detector), so
# merely standing on a vent is a ~flat cue once it is more than a pass-through.
VENT_CROSS_TICKS = 3  # ≤ this many ticks on a vent tile is just crossing it ⇒ neutral
VENT_DWELL_LOG_LR = math.log(8.0)

# body proximity — DECREASING in dwell: brief presence is the only window on a
# fleeing killer; a long camp at a corpse is (innocent) reporter behaviour. Full at
# first sight, fading linearly to 0 by BODY_FADE_TICKS.
BODY_NEAR_DIST = 16  # world px — "right next to it", not passing by
BODY_NEAR_LOG_LR = math.log(3.0)
BODY_FADE_TICKS = 48  # the log-LR fades to 0 over ~2 s of lingering

# follow-to-death — INCREASING in dwell (saturating): sustained shadowing of a player
# who then died is stalking. Gated on the target now being dead and the follow ending
# near the death.
FOLLOW_FULL_TICKS = 48  # the ramp reaches full at ~2 s of sustained proximity
FOLLOW_DEATH_WINDOW_TICKS = 72  # the follow ended ~within 3 s of finding the body
FOLLOW_LOG_LR = math.log(6.0)

# Accusations heard in meeting chat — another player saying "vote <color>". This is
# SOCIAL evidence, and it was the one signal the model had no term for at all: the
# perception layer already decodes chat into `belief.chat_log`, but nothing consumed it.
#
# These weights are MEASURED, not hand-picked. Over 619 accusation events in 320 hosted
# Crewrift Prime replays with exactly-known roles (roles forced via
# game_config_overrides.slots), a player named by k distinct accusers in a meeting was
# really an imposter:
#     k=1  54.9%  (n=576)  -> LR  3.04
#     k=2  86.8%  (n=38)   -> LR 16.50
#     k>=3 100%   (n=5)    -> LR inf; capped below, n is far too small to trust
# against a 28.6% prior (2 imposters among 7 others). See docs/suspicion-calibration.md.
#
# Deliberately, k=1 alone does NOT clear VOTE_PROBABILITY (0.4 prior odds x 3.04 = 1.22
# => p 0.55); 55% precision is not enough to eject someone. k=2 does (0.4 x 16.5 = 6.6
# => p 0.87), which is the intended behaviour: act when independent accusers converge.
#
# CAUTION: unlike the physical cues this one is adversarially manipulable — two imposters
# who both accuse the same crewmate would forge a k=2. That is not happening in the
# current field (86.8% precision at k=2), but re-measure whenever the field shifts.
ACCUSATION_LOG_LR: tuple[float, ...] = (
    0.0,              # k = 0, never accused
    math.log(3.04),   # k = 1
    math.log(16.5),   # k = 2
    math.log(24.0),   # k >= 3, capped (measured inf on n=5)
)
_ACCUSATION_RE = re.compile(r"\bvote\s+([a-z]+)\b", re.IGNORECASE)

# Flee a player once P(imposter) reaches this — a real probability, so the bar is
# interpretable (only near-certainty triggers the reactive Flee).
FLEE_PROBABILITY = 0.9
# Vote a player out once P(imposter) reaches this. Ejecting an innocent helps the
# imposters, so the bar sits below the (reactive) flee bar but still well above the
# prior — a vote is a deliberate, one-shot decision made with the meeting's full
# evidence.
#
# 2026-08-10: TRIED 0.65, REVERTED to 0.8 — see version_log.md (`watts:v2`). Lowering
# the bar worked mechanically (named-vote share 7% -> 50%, p=4.6e-12) but the extra
# votes were junk: accuracy fell 56% -> 20%, BELOW the ~29% random baseline, and
# innocent crewmates ejected went 4 -> 32 over 60 episodes. The posterior is
# well-calibrated at >=0.8 and ANTI-informative in the 0.65-0.8 band, so the fix
# belongs in the evidence weights above (BODY_NEAR/FOLLOW/VENT_DWELL log-LRs), not in
# this threshold. Don't re-lower it without recalibrating those first.
VOTE_PROBABILITY = 0.8
# Clamp the prior away from 0/1 so its log-odds stays finite.
PRIOR_MIN, PRIOR_MAX = 1e-3, 0.99

# Max distance a player can walk in one tick (MaxSpeed/MotionScale = 704/256 ≈ 2.75,
# rounded up): a player materialising inside a vent from beyond this vented.
VENT_WALK_MARGIN = 3


def update_suspicion(belief: Belief) -> None:
    """Recompute `suspicion` (posterior P(imp)) + `believed_imposters` each tick.

    Run after `update_belief`/`update_event_log` so the strategy snapshot is current.
    """

    if belief.self_role in ("imposter", "dead"):
        belief.suspicion = {}
        belief.believed_imposters = set()
        return
    _detect_witnessed_kill(belief)
    _detect_witnessed_vent(belief)
    _recompute(belief)


# --- prior ------------------------------------------------------------------


def _imposter_count(belief: Belief) -> int:
    if belief.imposter_count is not None:
        return belief.imposter_count
    total = belief.total_player_count
    return 0 if total < 5 else max(0, min((total - 3) // 2, total - 1))


def _prior_imposter_p(belief: Belief) -> float:
    n_others = max(1, belief.total_player_count - 1)
    return min(max(_imposter_count(belief) / n_others, PRIOR_MIN), PRIOR_MAX)


# --- tier 1: near-certain transitions → confirmed_imposters ------------------


def _frame_pair(belief: Belief) -> tuple[PerceptionFrame, PerceptionFrame] | None:
    """The (previous, current) tape frames, only if they are consecutive ticks."""

    frames = belief.recent_frames
    if len(frames) < 2:
        return None
    prev, curr = frames[-2], frames[-1]
    return (prev, curr) if curr.tick == prev.tick + 1 else None


def _detect_witnessed_kill(belief: Belief) -> None:
    pair = _frame_pair(belief)
    if pair is None:
        return
    prev, curr = pair
    for victim_color in curr.bodies:
        victim_pos = prev.players.get(victim_color)  # was this body's owner alive a frame ago?
        if victim_pos is None:
            continue
        killers = [
            color
            for color in neighbors_within(prev, victim_pos, KILL_RANGE_SQ, exclude=victim_color)
            if color not in belief.teammate_colors
        ]
        if len(killers) == 1:  # a single, unambiguous neighbour ⇒ the killer
            belief.confirmed_imposters.add(killers[0])


def _detect_witnessed_vent(belief: Belief) -> None:
    pair = _frame_pair(belief)
    if pair is None or belief.map is None:
        return
    prev, curr = pair
    for vent in belief.map.vents:
        x, y, w, h = vent.x, vent.y, vent.w, vent.h
        # (a) Emergence: vent + walk-margin in line of sight and clear last frame, occupied now.
        watched_clear = rect_visible(prev, x, y, w, h, margin=VENT_WALK_MARGIN) and not players_in_rect(
            prev, x, y, w, h, margin=VENT_WALK_MARGIN
        )
        if watched_clear:
            for color in players_in_rect(curr, x, y, w, h):
                belief.confirmed_imposters.add(color)
        # (b) Submersion: a player was in the vent last frame; vent still in sight, player gone.
        if rect_visible(curr, x, y, w, h):
            for color in players_in_rect(prev, x, y, w, h):
                if color not in curr.players:
                    belief.confirmed_imposters.add(color)


# --- tier 2: graded evidence from the event log -----------------------------


# --- per-event log-LR functions ---------------------------------------------
# Each maps one event's features → its log-likelihood-ratio contribution (0.0 =
# neutral). Simple closed forms; the constants above are the parameters.


def _vent_dwell_log_lr(event: PlayerEvent) -> float:
    return VENT_DWELL_LOG_LR if event.duration_ticks > VENT_CROSS_TICKS else 0.0


def _body_proximity_log_lr(event: PlayerEvent) -> float:
    if event.min_dist is None or event.min_dist > BODY_NEAR_DIST:
        return 0.0
    fade = max(0.0, 1.0 - event.duration_ticks / BODY_FADE_TICKS)  # brief ⇒ more suspicious
    return BODY_NEAR_LOG_LR * fade


def _follow_log_lr(event: PlayerEvent, belief: Belief) -> float:
    victim = belief.roster.get(event.target_color)
    if victim is None or victim.life_status != "dead" or victim.death_seen_tick is None:
        return 0.0
    if abs(victim.death_seen_tick - event.end_tick) > FOLLOW_DEATH_WINDOW_TICKS:
        return 0.0
    ramp = min(1.0, event.duration_ticks / FOLLOW_FULL_TICKS)  # longer shadowing ⇒ more
    return FOLLOW_LOG_LR * ramp


def _graded_log_lr(belief: Belief, record: PlayerRecord) -> float:
    """A player's total graded log-LR: the most-suspicious instance per evidence type.

    Aggregating with ``max`` (not a sum over every event) keeps each type's
    contribution bounded and double-count-free even with an unbounded event log.
    """

    vent = max((_vent_dwell_log_lr(e) for e in record.events if e.kind == "vent"), default=0.0)
    body = max((_body_proximity_log_lr(e) for e in record.events if e.kind == "near_body"), default=0.0)
    follow = max((_follow_log_lr(e, belief) for e in record.events if e.kind == "proximity"), default=0.0)
    return vent + body + follow


def _accusation_log_lr(belief: Belief, color: str) -> float:
    """log-LR from *distinct* players naming `color` in this meeting's chat.

    `belief.chat_log` is de-duplicated by (speaker, text) and cleared when a new
    meeting opens, so this scores only the current meeting. Counting **distinct
    accusers** (not messages) is what the calibration measured, and it stops one
    player repeating themselves from stacking evidence — the same bounded-contribution
    discipline as the `max`-per-type aggregation above.
    """
    accusers: set[str] = set()
    for event in belief.chat_log:
        speaker = event.speaker_color
        if speaker is None or speaker == color:
            continue  # unattributed line, or a player naming themselves
        if any(t.lower() == color for t in _ACCUSATION_RE.findall(event.text or "")):
            accusers.add(speaker)
    if not accusers:
        return 0.0
    return ACCUSATION_LOG_LR[min(len(accusers), len(ACCUSATION_LOG_LR) - 1)]


# --- combine into the posterior ---------------------------------------------


def _recompute(belief: Belief) -> None:
    prior_logit = _logit(_prior_imposter_p(belief))
    suspicion: dict[str, float] = {}
    believed: set[str] = set()

    for color in set(belief.roster) | belief.confirmed_imposters:
        record = belief.roster.get(color)
        if record is not None and record.life_status == "dead":
            continue  # the dead are no threat (the confirmation is kept for the record)
        logit = prior_logit
        if color in belief.confirmed_imposters:
            logit += WITNESSED_LOG_LR  # any near-certain catch — overwhelming
        if record is not None:
            logit += _graded_log_lr(belief, record)
        logit += _accusation_log_lr(belief, color)
        p = _sigmoid(logit)
        suspicion[color] = p
        if p >= FLEE_PROBABILITY:
            believed.add(color)

    belief.suspicion = suspicion
    belief.believed_imposters = believed


def top_suspect(belief: Belief) -> str | None:
    """The live player to vote out — highest posterior P(imp) over `VOTE_PROBABILITY`,
    or `None` (skip) when no one is suspicious enough. Used by Attend Meeting (§7.1)."""

    if not belief.suspicion:
        return None
    color, p = max(belief.suspicion.items(), key=lambda kv: kv[1])
    return color if p >= VOTE_PROBABILITY else None


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(logit: float) -> float:
    logit = max(-700.0, min(700.0, logit))  # keep exp finite
    return 1.0 / (1.0 + math.exp(-logit))
