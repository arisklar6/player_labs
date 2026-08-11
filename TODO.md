# player_labs — deferred tasks

Tasks intentionally parked to handle later. Add items here when you defer something
mid-session; check them back at the start of focused work.

## Open

- **Apply the measured `body_proximity` / `follow_to_death` LRs** (1.36 and 2.51, vs the
  hand-estimated 3 and 6). Measured 2026-08-10 over 320 replays; recorded in
  `crewrift_lab/crewrift/crewborg/docs/designs/suspicion.md` §7 but deliberately not
  applied, because correcting them downward makes crewborg vote *less* rather than
  better. Do it as a correctness pass — and re-measure at pixel resolution first, since
  the room-level proxy used is conservative. Full analysis:
  `crewrift_lab/crewrift/crewborg/docs/suspicion-calibration.md`.
- **Crewmate survival.** crewborg dies in 65–73% of forced-crew episodes vs ~10–15% as
  imposter. `FLEE_PROBABILITY = 0.9` is stricter than the vote bar that was just proven
  too strict, so it likely almost never flees. Untested direction, own experiment.
- **Re-measure accusation precision when the field shifts.** `ACCUSATION_LOG_LR` is the
  only adversarially manipulable cue (two imposters can forge a k=2 accusation). Current
  k=2 precision 86.8%; re-run `accuse.py`-style measurement periodically.
- **Exclude own policies from opponent pools.** Experience requests draw `top_n`
  champions, and Ari owns `arisk-crewrift-crewborg` in the same division. If it is drawn,
  two seats share the owner display name and the replay-based analysis can't map
  owner → colour, so those episodes get skipped. Use `excluded_players` in the request
  body to avoid it.

- **Test whether the suspicion model degrades with 2 imposters.** v2's votes were 2.2x
  better than random in the 1-imposter `crewrift-prime-vote-basic` drill but 0.7x
  (anti-informative) in 2-imposter league play. Isolate it by running the drill with
  `game_config_overrides.imposterCount = 2` against the same field. If confirmed, the
  co-location evidence needs to be conditioned on the imposter count, and every
  1-imposter drill result is optimistic.

## Done

_None yet._
