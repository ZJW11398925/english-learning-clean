"""The World Run's seven-step sequence, declared (spec §4.2 v2.1).

The seven steps are the run's *structure*, not seven functions. Step 1
is the caller's act — the user's reply winds the spring and is the only
run starter (spec §4.1); the engine never starts itself. Steps 2–5 are
the deterministic body :mod:`elc.world.engine.engine` executes per
cycle. Steps 6–7 are the presentation halves this cut **declares and
does not simulate**: rendering follows the visibility settings
(spec §4.5) and the terminal wait is the world's silent survival — both
belong to the presentation cuts that follow, and nothing here pretends
to do them (the banner's honesty lists carry the same words).
"""

from __future__ import annotations

__all__ = [
    "STEPS",
    "STEP_COMMS",
    "STEP_EVENTS",
    "STEP_MOMENT",
    "STEP_RENDER",
    "STEP_TIME",
    "STEP_WAIT",
    "STEP_WINCH",
]

#: Step 1 — 发条 (the winch): the user's reply is the only run starter
#: (spec §4.1). A run exists because a caller created it against a
#: trigger (``trigger_turn_id`` on the row); ``advance`` only ever
#: continues a run that exists, and «继续» / a direction choice are the
#: same run's resumed execution — never a second winch.
STEP_WINCH = "1-winch"

#: Step 2 — 时间推进: the world's calendar moves ``days_per_cycle`` per
#: cycle. This cut keeps no world calendar — the count is recorded in
#: the cycle trace, and nothing pretends to be a clock.
STEP_TIME = "2-time-advance"

#: Step 3 — 事件判定: the pool's mature events (every condition
#: CURRENT-matching the state projection) are the candidates, in pool
#: order; the per-cycle RNG — seeded (seed, cursor) — picks one.
STEP_EVENTS = "3-event-maturity"

#: Step 4 — 通信编排 (v1): at most one actor of the world writes or the
#: world stays silent — decided by one further draw from the same
#: per-cycle RNG and recorded in the trace only. No letters are
#: generated (zero model face this cut); the real correspondence is a
#: later cut's work.
STEP_COMMS = "4-communication"

#: Step 5 — 时刻判定 (the double exit): the selected event's moment is
#: the call's exit — NOTICE pauses the run at its checkpoint (the same
#: run resumes on the user's light action), RESPONSE terminates it
#: (spec §4.2 step 5, v2.1).
STEP_MOMENT = "5-moment"

#: Step 6 — 呈现渲染: DECLARED, NOT SIMULATED. Rendering the run's
#: process and result per the visibility settings is the presentation
#: cut's work (Revisit W-2-x); this cut writes structural traces, not
#: prose for a reader.
STEP_RENDER = "6-render"

#: Step 7 — 等待 (terminal only): DECLARED, NOT SIMULATED. The world's
#: silent survival between runs needs no code here — the TERMINAL row
#: itself is the waiting; the reveal face that surfaces what a finished
#: run left behind is W-1-3's registered cut.
STEP_WAIT = "7-wait"

#: The seven steps, in order — the run's structure (spec §4.2).
STEPS: tuple[str, ...] = (
    STEP_WINCH,
    STEP_TIME,
    STEP_EVENTS,
    STEP_COMMS,
    STEP_MOMENT,
    STEP_RENDER,
    STEP_WAIT,
)
