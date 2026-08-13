"""Near-certain suspicion tests: witnessed kill + witnessed vent (design §10.1)."""

from __future__ import annotations

import numpy as np
import pytest

from crewrift.crewborg.map.types import MapData, MapPoint, MapRect, Vent
from crewrift.crewborg.strategy.suspicion import (
    BODY_FADE_TICKS,
    FLEE_PROBABILITY,
    FOLLOW_FULL_TICKS,
    VENT_CROSS_TICKS,
    VOTE_PROBABILITY,
    imposter_vote_target,
    top_suspect,
    update_suspicion,
)
from crewrift.crewborg.types import (
    Belief,
    ChatEvent,
    PerceptionFrame,
    PlayerEvent,
    PlayerRecord,
)


def _frame(tick: int, players=None, bodies=None, camera=(0, 0), mask=None) -> PerceptionFrame:
    return PerceptionFrame(
        tick=tick, camera_x=camera[0], camera_y=camera[1],
        players=dict(players or {}), bodies=dict(bodies or {}), visible_mask=mask,
    )


def _belief(prev: PerceptionFrame, curr: PerceptionFrame, **kwargs) -> Belief:
    kwargs.setdefault("self_role", "crewmate")
    return Belief(last_tick=curr.tick, recent_frames=[prev, curr], **kwargs)


def _vent_map() -> MapData:
    return MapData(
        width=200, height=200, tasks=(),
        vents=(Vent(x=50, y=50, w=8, h=8, group="g", group_index=1),),  # rect [50,58)x[50,58)
        rooms=(), button=MapRect(x=0, y=0, w=4, h=4), home=MapPoint(x=10, y=10),
    )


# --- witnessed kill ---------------------------------------------------------


def test_lone_neighbor_of_a_just_killed_victim_is_confirmed() -> None:
    prev = _frame(4, players={"red": (100, 100), "green": (110, 100)})  # together, alive
    curr = _frame(5, players={"green": (110, 100)}, bodies={"red": (100, 100)})  # red now a body
    belief = _belief(prev, curr)
    update_suspicion(belief)
    assert "green" in belief.believed_imposters


def test_kill_is_not_attributed_when_two_players_were_in_range() -> None:
    prev = _frame(4, players={"red": (100, 100), "green": (110, 100), "blue": (115, 100)})
    curr = _frame(5, players={"green": (110, 100), "blue": (115, 100)}, bodies={"red": (100, 100)})
    belief = _belief(prev, curr)
    update_suspicion(belief)
    assert not belief.believed_imposters  # ambiguous → no accusation


def test_kill_with_no_visible_neighbor_implicates_no_one() -> None:
    prev = _frame(4, players={"red": (100, 100), "green": (200, 100)})  # green far (>kill range)
    curr = _frame(5, players={"green": (200, 100)}, bodies={"red": (100, 100)})
    belief = _belief(prev, curr)
    update_suspicion(belief)
    assert not belief.believed_imposters


def test_non_consecutive_frames_are_not_read_as_a_kill() -> None:
    prev = _frame(2, players={"red": (100, 100), "green": (110, 100)})  # a meeting-sized gap
    curr = _frame(5, players={"green": (110, 100)}, bodies={"red": (100, 100)})
    belief = _belief(prev, curr)
    update_suspicion(belief)
    assert not belief.believed_imposters


def test_imposter_observer_accrues_no_suspicion() -> None:
    prev = _frame(4, players={"red": (100, 100), "green": (110, 100)})
    curr = _frame(5, players={"green": (110, 100)}, bodies={"red": (100, 100)})
    belief = _belief(prev, curr, self_role="imposter")
    update_suspicion(belief)
    assert not belief.suspicion and not belief.believed_imposters


# --- witnessed vent: emergence (a) ------------------------------------------


def test_player_emerging_into_a_watched_clear_vent_is_confirmed() -> None:
    prev = _frame(4, players={}, camera=(0, 0))  # vent + margin in view, no one near it
    curr = _frame(5, players={"red": (53, 53)}, camera=(0, 0))  # now inside the vent rect
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert "red" in belief.believed_imposters


def test_emergence_requires_the_vent_to_have_been_watched() -> None:
    prev = _frame(4, players={}, camera=(400, 400))  # vent off-screen last frame
    curr = _frame(5, players={"red": (53, 53)}, camera=(0, 0))
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters  # we weren't watching → can't conclude emergence


def test_a_player_near_the_vent_last_frame_blocks_an_emergence_call() -> None:
    prev = _frame(4, players={"red": (48, 53)}, camera=(0, 0))  # within the walk margin of the vent
    curr = _frame(5, players={"red": (53, 53)}, camera=(0, 0))  # could have walked in
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters


# --- witnessed vent: submersion (b) -----------------------------------------


def test_player_vanishing_from_a_visible_vent_is_confirmed() -> None:
    prev = _frame(4, players={"red": (53, 53)}, camera=(0, 0))  # standing in the vent rect
    curr = _frame(5, players={}, camera=(0, 0))  # gone, but the vent is still in view
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert "red" in belief.believed_imposters


def test_submersion_requires_the_vent_to_still_be_in_view() -> None:
    prev = _frame(4, players={"red": (53, 53)}, camera=(0, 0))
    curr = _frame(5, players={}, camera=(400, 400))  # vent off-screen now → maybe just walked off
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters


def test_a_player_standing_on_a_vent_is_not_a_venter() -> None:
    prev = _frame(4, players={"red": (53, 53)}, camera=(0, 0))
    curr = _frame(5, players={"red": (54, 53)}, camera=(0, 0))  # still visible on the vent
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters


# --- line-of-sight gating (the decoded shadow mask) -------------------------


def test_emergence_is_suppressed_when_the_vent_is_occluded() -> None:
    occluded = np.ones((128, 128), dtype=bool)
    occluded[47:61, 47:61] = False  # vent + walk margin out of line of sight
    prev = _frame(4, players={}, camera=(0, 0), mask=occluded)  # "clear" only because occluded
    curr = _frame(5, players={"red": (53, 53)}, camera=(0, 0), mask=np.ones((128, 128), dtype=bool))
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters  # couldn't actually see the vent was clear


def test_emergence_fires_when_the_vent_is_truly_in_sight() -> None:
    lit = np.ones((128, 128), dtype=bool)
    prev = _frame(4, players={}, camera=(0, 0), mask=lit)
    curr = _frame(5, players={"red": (53, 53)}, camera=(0, 0), mask=lit)
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert "red" in belief.believed_imposters


def test_submersion_is_suppressed_when_the_vent_is_occluded_now() -> None:
    prev = _frame(4, players={"red": (53, 53)}, camera=(0, 0), mask=np.ones((128, 128), dtype=bool))
    occluded = np.ones((128, 128), dtype=bool)
    occluded[50:58, 50:58] = False  # the vent is no longer in sight this frame
    curr = _frame(5, players={}, camera=(0, 0), mask=occluded)
    belief = _belief(prev, curr, map=_vent_map())
    update_suspicion(belief)
    assert not belief.believed_imposters  # player gone, but maybe they just walked behind a wall


# --- Bayesian posterior: prior + per-event graded log-LRs (tier 2) ----------


def _vent_dwell(start: int = 1, dur: int = 10) -> PlayerEvent:
    return PlayerEvent(kind="vent", start_tick=start, end_tick=start + dur, region_index=0)


def _near_body(start: int = 50, dur: int = 1, dist: int = 8) -> PlayerEvent:
    return PlayerEvent(
        kind="near_body", start_tick=start, end_tick=start + dur, target_color="blue", min_dist=dist
    )


def _long_follow(start: int = 40, target: str = "yellow") -> PlayerEvent:
    return PlayerEvent(
        kind="proximity", start_tick=start, end_tick=start + FOLLOW_FULL_TICKS, target_color=target, min_dist=10
    )


def _crew_belief(total_players: int = 8) -> Belief:
    # A neutral crewmate scene with a known player count, so the prior is meaningful.
    return Belief(self_role="crewmate", last_tick=200, total_player_count=total_players)


def _add(belief: Belief, color: str, events=()) -> None:
    belief.roster[color] = PlayerRecord(color=color, life_status="alive", events=list(events))


def test_no_evidence_player_sits_at_the_combinatorial_prior() -> None:
    belief = _crew_belief(total_players=8)  # 8 players ⇒ 2 imposters among the other 7
    _add(belief, "red")
    update_suspicion(belief)
    assert belief.suspicion["red"] == pytest.approx(2 / 7)
    assert "red" not in belief.believed_imposters


def test_one_graded_signal_raises_the_posterior_but_does_not_flee() -> None:
    belief = _crew_belief()
    _add(belief, "red", [_vent_dwell()])
    _add(belief, "blue")  # a no-evidence baseline
    update_suspicion(belief)
    assert belief.suspicion["red"] > belief.suspicion["blue"]  # evidence moved the posterior up
    assert "red" not in belief.believed_imposters  # ...but a single cue isn't near-certain


def test_corroborating_graded_signals_cross_the_flee_bar() -> None:
    belief = _crew_belief()
    _add(belief, "red", [_vent_dwell(), _long_follow()])
    belief.roster["yellow"] = PlayerRecord(color="yellow", life_status="dead", death_seen_tick=40 + FOLLOW_FULL_TICKS)
    update_suspicion(belief)
    assert belief.suspicion["red"] >= FLEE_PROBABILITY and "red" in belief.believed_imposters


def test_body_proximity_is_more_suspicious_when_brief_than_when_camped() -> None:
    # A skilled imposter flees; a long camp at a corpse is reporter behaviour. So the
    # body-proximity log-LR DECREASES with dwell — the headline of the per-event shape.
    belief = _crew_belief()
    _add(belief, "red", [_near_body(dur=1)])  # a brief glimpse next to the body
    _add(belief, "green", [_near_body(dur=BODY_FADE_TICKS)])  # camped until the cue fades to 0
    _add(belief, "blue")  # baseline (prior)
    update_suspicion(belief)
    assert belief.suspicion["red"] > belief.suspicion["green"]
    assert belief.suspicion["green"] == pytest.approx(belief.suspicion["blue"])  # long camp ⇒ neutral


def test_pass_through_and_distant_cues_are_neutral() -> None:
    belief = _crew_belief()
    _add(belief, "red", [
        _vent_dwell(dur=VENT_CROSS_TICKS - 1),  # duration = VENT_CROSS_TICKS ⇒ just crossing the tile
        _near_body(dur=1, dist=40),  # too far from the body
        PlayerEvent(kind="proximity", start_tick=20, end_tick=24, target_color="green", min_dist=5),  # victim alive
    ])
    _add(belief, "blue")  # baseline
    update_suspicion(belief)
    assert belief.suspicion["red"] == pytest.approx(belief.suspicion["blue"])  # nothing moved the prior


def test_following_a_victim_to_death_only_updates_when_they_died() -> None:
    alive = _crew_belief()
    _add(alive, "orange", [_long_follow()])
    _add(alive, "yellow")  # victim still alive ⇒ no evidence
    update_suspicion(alive)
    assert alive.suspicion["orange"] == pytest.approx(alive.suspicion["yellow"])  # both at the prior

    dead = _crew_belief()
    _add(dead, "orange", [_long_follow()])
    dead.roster["yellow"] = PlayerRecord(color="yellow", life_status="dead", death_seen_tick=40 + FOLLOW_FULL_TICKS)
    update_suspicion(dead)
    assert dead.suspicion["orange"] > 2 / 7  # following the victim to death raised it above prior


def test_dead_subjects_drop_out_of_the_posterior() -> None:
    belief = _crew_belief()
    _add(belief, "red", [_vent_dwell()])
    belief.roster["red"].life_status = "dead"
    update_suspicion(belief)
    assert "red" not in belief.suspicion  # the dead are no threat


def test_a_confirmation_drives_the_posterior_to_near_one() -> None:
    belief = _belief(_frame(4, players={}), _frame(5, players={"red": (53, 53)}), map=_vent_map())
    belief.total_player_count = 8
    update_suspicion(belief)  # emergence ⇒ confirmed
    assert "red" in belief.confirmed_imposters and "red" in belief.believed_imposters
    assert belief.suspicion["red"] > 0.99  # overwhelming likelihood ratio


# --- believed-imposters maintenance -----------------------------------------


def test_a_confirmed_imposter_is_cleared_once_dead() -> None:
    prev = _frame(4, players={"red": (53, 53)}, camera=(0, 0))
    curr = _frame(5, players={}, camera=(0, 0))
    belief = _belief(prev, curr, map=_vent_map())
    belief.roster["red"] = PlayerRecord(color="red", life_status="alive")
    update_suspicion(belief)
    assert "red" in belief.believed_imposters

    belief.roster["red"].life_status = "dead"
    update_suspicion(belief)
    assert "red" not in belief.believed_imposters


# --- top_suspect (voting target) --------------------------------------------


def test_top_suspect_picks_the_highest_over_the_vote_bar() -> None:
    belief = Belief(self_role="crewmate")
    belief.suspicion = {"red": VOTE_PROBABILITY + 0.05, "blue": 0.99}
    assert top_suspect(belief) == "blue"  # the most suspicious clears the bar


def test_top_suspect_returns_none_below_the_vote_bar() -> None:
    belief = Belief(self_role="crewmate")
    belief.suspicion = {"red": VOTE_PROBABILITY - 0.05, "blue": 0.1}
    assert top_suspect(belief) is None  # nobody confident enough ⇒ skip


# --- meeting-chat accusations (docs/suspicion-calibration.md) ---------------


def _chat_belief(*lines: tuple[str, str], total: int = 8) -> Belief:
    """A crewmate belief with a roster of 8 and `lines` of (speaker, text) chat."""
    roster = {c: PlayerRecord(color=c) for c in
              ("red", "green", "blue", "cyan", "pink", "purple", "orange")}
    return Belief(
        last_tick=100, self_role="crewmate", total_player_count=total, roster=roster,
        chat_log=[ChatEvent(tick=90 + i, speaker_color=s, text=t)
                  for i, (s, t) in enumerate(lines)],
    )


def test_one_accuser_raises_suspicion_but_does_not_reach_the_vote_bar() -> None:
    belief = _chat_belief(("green", "cyan sus: tailing me. vote cyan"))
    update_suspicion(belief)
    # 55% precision measured at k=1 — enough to notice, not enough to eject.
    assert belief.suspicion["cyan"] > belief.suspicion["pink"]
    assert belief.suspicion["cyan"] < VOTE_PROBABILITY
    assert top_suspect(belief) is None


def test_two_distinct_accusers_clear_the_vote_bar() -> None:
    belief = _chat_belief(
        ("green", "cyan sus: tailing me. vote cyan"),
        ("blue", "agreed, vote cyan"),
    )
    update_suspicion(belief)
    assert belief.suspicion["cyan"] >= VOTE_PROBABILITY
    assert top_suspect(belief) == "cyan"


def test_one_player_repeating_themselves_is_still_one_accuser() -> None:
    belief = _chat_belief(
        ("green", "cyan sus. vote cyan"),
        ("green", "seriously, vote cyan"),
        ("green", "everyone vote cyan now"),
    )
    update_suspicion(belief)
    assert belief.suspicion["cyan"] < VOTE_PROBABILITY  # distinct accusers, not messages
    assert top_suspect(belief) is None


def test_self_accusation_is_ignored() -> None:
    belief = _chat_belief(("cyan", "not me, vote cyan is wrong"))
    update_suspicion(belief)
    assert belief.suspicion["cyan"] == pytest.approx(belief.suspicion["pink"])


def test_unattributed_chat_line_is_ignored() -> None:
    belief = _chat_belief((None, "vote cyan"))  # type: ignore[arg-type]
    update_suspicion(belief)
    assert belief.suspicion["cyan"] == pytest.approx(belief.suspicion["pink"])


def test_an_imposter_ignores_meeting_accusations() -> None:
    belief = _chat_belief(
        ("green", "vote cyan"), ("blue", "vote cyan"),
    )
    belief.self_role = "imposter"
    update_suspicion(belief)
    assert belief.suspicion == {}  # imposters know the truth; no suspicion model


# --- imposter voting (docs/suspicion-calibration.md §5) ---------------------


def _imp_belief(*lines: tuple[str, str], teammates=("blue",)) -> Belief:
    roster = {c: PlayerRecord(color=c) for c in
              ("red", "green", "blue", "cyan", "pink", "purple", "orange")}
    return Belief(
        last_tick=100, self_role="imposter", total_player_count=8, roster=roster,
        teammate_colors=set(teammates),
        chat_log=[ChatEvent(tick=90 + i, speaker_color=s, text=t)
                  for i, (s, t) in enumerate(lines)],
    )


_CANDS = {"green", "blue", "cyan", "pink", "purple", "orange"}


def test_imposter_never_votes_its_teammate() -> None:
    belief = _imp_belief(("green", "vote blue"), ("cyan", "vote blue"), teammates=("blue",))
    # the crowd is accusing our teammate; we must not pile on
    assert imposter_vote_target(belief, _CANDS) != "blue"


def test_imposter_bandwagons_onto_the_most_accused_crewmate() -> None:
    belief = _imp_belief(
        ("green", "vote pink"), ("cyan", "vote pink"), ("orange", "vote purple"),
        teammates=("blue",),
    )
    assert imposter_vote_target(belief, _CANDS) == "pink"


def test_imposter_still_votes_when_nobody_is_accused() -> None:
    belief = _imp_belief(teammates=("blue",))
    target = imposter_vote_target(belief, _CANDS)
    assert target is not None and target != "blue"   # never skip, never a teammate


def test_imposter_has_no_target_when_only_teammates_remain() -> None:
    belief = _imp_belief(teammates=("blue", "cyan"))
    assert imposter_vote_target(belief, {"blue", "cyan"}) is None


# --- imposter bandwagon patterns (measured; see suspicion.py BANDWAGON_PATTERNS) ------


def test_imposter_bandwagons_on_the_sus_phrasing_not_just_vote() -> None:
    # "<C> sus" is 4.2x more common than "vote <C>" and converts at 42% vs a 26.6% fallback
    belief = _imp_belief(("green", "pink sus: they were tailing me"), teammates=("blue",))
    assert imposter_vote_target(belief, _CANDS) == "pink"


def test_imposter_does_not_accuse_the_corpse_named_in_the_message() -> None:
    # "pink sus: next to purple's body" accuses pink; purple is the victim, not a suspect
    belief = _imp_belief(("green", "pink sus: next to purple's body"), teammates=("blue",))
    assert imposter_vote_target(belief, _CANDS) == "pink"


def test_saw_kill_outranks_more_numerous_sus_claims() -> None:
    # tier beats accuser count: one 75%-converting claim over two 42% ones
    belief = _imp_belief(
        ("green", "cyan sus: they were tailing me"),
        ("orange", "cyan sus: lurking on a vent"),
        ("purple", "saw pink kill orange"),
        teammates=("blue",),
    )
    assert imposter_vote_target(belief, _CANDS) == "pink"


def test_vented_phrasing_is_ignored_it_converts_no_better_than_the_fallback() -> None:
    belief = _imp_belief(("green", "purple vented at tick 900"), teammates=("blue",))
    # no usable signal -> deterministic fallback, NOT the vent claim
    assert imposter_vote_target(belief, _CANDS) == sorted(_CANDS - {"blue"})[0]


def test_crew_accusation_cue_still_uses_only_the_strict_vote_pattern() -> None:
    # widening is imposter-only; the crew posterior's weights were calibrated on "vote <C>"
    belief = _chat_belief(("green", "cyan sus: they were tailing me"))
    update_suspicion(belief)
    assert belief.suspicion["cyan"] == pytest.approx(belief.suspicion["pink"])
