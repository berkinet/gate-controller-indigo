# -*- coding: utf-8 -*-

"""Transport-neutral gate motion state machine."""

from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on", "closed", "active"}
FALSE_VALUES = {"0", "false", "no", "off", "open", "inactive", ""}


def input_active(value, active_when="true"):
    """Interpret common Indigo state values using configurable polarity."""
    if isinstance(value, bool):
        active = value
    elif isinstance(value, (int, float)):
        active = value != 0
    else:
        text = str(value).strip().lower()
        if text in TRUE_VALUES:
            active = True
        elif text in FALSE_VALUES:
            active = False
        else:
            try:
                active = float(text) != 0
            except ValueError:
                active = False
    return active if str(active_when).lower() == "true" else not active


@dataclass(frozen=True)
class Transition:
    old: str
    new: str
    reason: str


class GateStateMachine:
    """Classify lamp edges while allowing physical limits to dominate."""

    VALID_STATES = {"unknown", "opening", "closing", "open", "closed",
                    "stopped", "fault", "paused"}

    def __init__(self, debounce=0.10, idle_timeout=2.5, fast=0.80,
                 slow=1.60, band=0.10):
        self.debounce = float(debounce)
        self.idle_timeout = float(idle_timeout)
        self.fast = float(fast)
        self.slow = float(slow)
        self.band = float(band)
        self.state = "unknown"
        self.last_interval = None
        self.last_edge = None
        self.last_lamp_active = False
        self.last_motion = "unknown"
        self.idle_deadline = None
        self.paused_until = 0.0

    def synchronize(self, now, lamp_active, open_active, closed_active):
        """Establish startup input levels without inventing a lamp edge."""
        self.last_lamp_active = bool(lamp_active)
        self.last_edge = None
        self.last_interval = None
        self.last_motion = "unknown"
        self.idle_deadline = None
        self.paused_until = 0.0
        if open_active and closed_active:
            return self._transition("fault", "both limits active at startup")
        if open_active:
            return self._transition("open", "open limit active at startup")
        if closed_active:
            return self._transition("closed", "closed limit active at startup")
        return self._transition("unknown", "position unknown at startup")

    def _transition(self, new_state, reason):
        if new_state == self.state:
            return None
        change = Transition(self.state, new_state, reason)
        self.state = new_state
        return change

    def force(self, state, now, pause_seconds=0.0):
        if state not in self.VALID_STATES:
            raise ValueError("invalid gate state: %s" % state)
        self.paused_until = float(now) + max(0.0, float(pause_seconds))
        self.last_edge = None
        self.last_interval = None
        self.last_motion = "unknown"
        self.idle_deadline = None
        return self._transition(state, "forced")

    def observe(self, now, lamp_active, open_active, closed_active):
        now = float(now)
        lamp_active = bool(lamp_active)
        rising_edge = lamp_active and not self.last_lamp_active
        self.last_lamp_active = lamp_active

        if open_active and closed_active:
            self.idle_deadline = None
            return self._transition("fault", "both limits active")
        if open_active:
            self.last_motion = "unknown"
            self.idle_deadline = None
            return self._transition("open", "open limit active")
        if closed_active:
            self.last_motion = "unknown"
            self.idle_deadline = None
            return self._transition("closed", "closed limit active")
        if now < self.paused_until:
            return None
        if not rising_edge:
            return None
        if self.last_edge is not None and now - self.last_edge < self.debounce:
            return None

        interval = None if self.last_edge is None else now - self.last_edge
        self.last_edge = now
        self.last_interval = interval
        self.idle_deadline = now + self.idle_timeout
        if interval is None or interval > self.idle_timeout:
            self.last_motion = "unknown"
            return self._transition("unknown", "first lamp pulse")
        if abs(interval - self.fast) <= self.band:
            self.last_motion = "closing"
            return self._transition("closing", "fast lamp pulse")
        if abs(interval - self.slow) <= self.band:
            self.last_motion = "opening"
            return self._transition("opening", "slow lamp pulse")
        return None

    def idle(self, now, open_active=False, closed_active=False):
        now = float(now)
        if self.idle_deadline is None or now < self.idle_deadline:
            return None
        self.idle_deadline = None
        if open_active and closed_active:
            return self._transition("fault", "both limits active at idle")
        if open_active:
            return self._transition("open", "open limit active at idle")
        if closed_active:
            return self._transition("closed", "closed limit active at idle")
        if self.last_motion == "opening":
            return self._transition("open", "lamp pulses stopped after opening")
        if self.last_motion == "closing":
            return self._transition("closed", "lamp pulses stopped after closing")
        return self._transition("stopped", "lamp pulses stopped without classification")
