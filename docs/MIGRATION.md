# Migration plan from the current gate automation

This plan is intentionally reversible. The alpha plugin is first installed as
an observer, then downstream automations are moved one at a time. Nothing in
this repository edits the live Indigo database.

## Current elements identified

- The `GiBiDi SPIA` lamp pulse trigger calls `gate_motion.gateLamp.lamp_edge()`.
- `gate_motion.py` derives `opening`, `closing`, `open`, and `closed` using the
  `GateMotion`, `GateLampDt`, and `GateLampDebug` variables.
- `GateOpenLimit` and `GateCloseLimit` represent the physical end stops.
- Existing triggers use motion transitions for announcements, lights, and the
  open-too-long alarm; the closed transition cancels that alarm.
- The kitchen lamp mirror and Variable Mirror device expose derived state to
  other automations and HomeKit.
- `House - gate control` is the existing momentary gate control output.
- Debug and manual state triggers currently support testing and recovery.

Names above are migration references, not hard-coded plugin dependencies. Every
source is selected in the Gate Controller device configuration.

## Staged cutover

1. **Observer phase:** Install the plugin, configure required inputs, and leave
   all existing gate scripts and triggers enabled. Do not configure the control
   output yet. Compare plugin state with `GateMotion` over multiple full cycles.
2. **Event phase:** Create new disabled Indigo triggers for plugin events. Copy
   announcements, lighting, and other house-specific actions from the existing
   triggers. Enable and validate them one category at a time while disabling
   only the exact legacy trigger they replace.
3. **Timer phase:** Move the open-too-long workflow to the plugin's event or
   Action Group hook. Verify that closing cancels the condition before removing
   the legacy timer logic.
4. **HomeKit phase:** Point HomeKit integration at the plugin's Garage
   Controller device and verify all five `doorState` values. Retire Variable
   Mirror only after open, close, moving, and stopped behavior is confirmed.
5. **Control phase:** Configure `House - gate control`, test one supervised
   pulse, then move gate-control callers to the plugin device/action.
6. **Cleanup phase:** Disable the `GiBiDi SPIA` Python trigger and the old debug
   triggers. Leave them disabled through a proving period before deleting the
   script, variables, or triggers.

## Suggested plugin-device functions versus Indigo actions

Keep these in the plugin:

- Reading configured detector states and polarity.
- Classifying flash intervals and resolving physical limits.
- Publishing authoritative gate/HomeKit state.
- Open-too-long timing, state, and transition event.
- Fault detection and source-input health.
- A server-managed momentary pulse to the configured control device.

Keep these as Indigo trigger actions:

- Spoken announcements and quiet-hours policy.
- Which lights turn on, their duration, and daylight conditions.
- Email/push recipients and message wording.
- Camera snapshots and retention.
- Occupancy, security-mode, and presence-dependent decisions.

This boundary lets the plugin describe what the gate did while Indigo decides
what the house should do about it.
