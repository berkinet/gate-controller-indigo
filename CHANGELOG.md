# Changelog

## Unreleased

## 0.1.0-beta.7 — 2026-09-12

- Give unavailable gate inputs a short warning grace period so ordinary
  Phidgets plugin restarts do not produce alarming transient warnings.
- Continue to mark inputs unavailable immediately, and retain warnings when
  the input failure persists beyond the grace period.

## 0.1.0-beta.6 — 2026-09-12

- Coalesce input updates while required gate inputs recover, then establish one
  silent state-machine baseline after the input set has settled.
- Prevent staggered Phidget state restoration during a plugin restart from
  producing false Opening/Closed transitions, Gate Controller events, or gate
  action-group execution.
- Preserve immediate evaluation and notification for normal input changes once
  all required inputs are available.

## 0.1.0-beta.5 — 2026-09-10

- Document measured BA230 Lock1/Lock2 activation envelopes, their ordering and
  timing relative to SPIA and the first-leaf position limits, supported
  diagnostic inferences, electrical-measurement uncertainty, and the decision
  not to make the lock signals operational state inputs based on one session.

## 0.1.0-beta.4 — 2026-09-09

- Split estimated second-leaf completion into independent opening and closing
  delays, defaulting to 10 and 0 seconds. Legacy single-delay values remain
  compatible as the opening delay.

## 0.1.0-beta.3 — 2026-09-09

- Add a default-on second-leaf delay mode that keeps the gate Opening or
  Closing for a configurable interval after the first-leaf endpoint. The delay
  is canceled if that limit releases or motion changes.
- Make delayed estimation and physical second-leaf limits mutually exclusive
  in the device configuration, revealing only the selected strategy.

## 0.1.0-beta.2 — 2026-09-09

- Add a Detailed debugging logging level containing the former Debugging
  diagnostics, and make Debugging a concise timeline of configured non-lock
  input edges and gate-state changes. Lock activity remains available through
  Indigo states and Detailed debugging without flooding the normal debug log.
- Add continuous integration for the unit suite and branch-coverage reporting.
- Document the main Indigo lifecycle and runtime boundaries, with focused type
  hints for configuration helpers.
- Consolidate source-device and state lookup used by configuration validation.
- Add contributor guidance for testing, architecture, manifests, releases, and
  security-sensitive data.
- Record the public-repository secret scan and enable GitHub secret scanning
  and push protection.

## 0.1.0-beta.1 — 2026-09-09

- Add an optional Gate Status Indicator output that follows the live
  SPIA/flashing-lamp signal while the gate operates, remains steadily on while
  the authoritative gate state is Open (including forced/locked open), and
  turns off while Closed.
- Add configurable indicator-output inversion and prevent the indicator from
  reusing a gate input, the command output, or the Gate Controller itself.
- Synchronize the indicator at startup, suppress redundant output commands,
  and isolate repeated indicator failures from gate sensing with deduplicated
  warnings and automatic retry.
- Promote the plugin from alpha to beta after completing the legacy gate-script
  replacement surface.

## 0.1.0-alpha.9 — 2026-09-09

- Add a four-level plugin logging preference: Debugging, Informational,
  Warning, and Error, with Informational as the default.
- Limit routine informational output to `Gate opening` and `Gate closed.`;
  startup synchronization, input recovery, full transitions, actions, and
  lifecycle details now appear only at Debugging.
- Add Debugging diagnostics for input snapshots, limit overrides, accepted and
  debounced lamp pulses, pulse classification, timer activity, forced states,
  trigger execution, and control pulses.
- Report conflicting limits and the open-too-long condition as warnings while
  retaining existing input-unavailable warnings and operational errors.

## 0.1.0-alpha.8 — 2026-09-09

- Infer Opening immediately when the first lamp pulse follows departure from
  the closed limit, and Closing when it follows departure from the open limit.
  This avoids a transient Unknown state that HomeKitLink presents as a sticky
  obstruction during otherwise normal travel.
- Display Indigo's Locked image only while fully closed and Unlocked while
  open, opening, closing, stopped, unknown, paused, or faulted.

## 0.1.0-alpha.7 — 2026-09-09

- Pass the momentary pulse duration to Indigo as the required unsigned whole
  number, fixing the Boost.Python argument mismatch that prevented operation.
- Validate pulse duration as a positive whole number in the device dialog.
- Remove the misleading stateful power icon while preserving the native Toggle
  command and Garage Controller/HomeKit behavior.

## 0.1.0-alpha.6 — 2026-09-09

- Restore Indigo's standard device reconfiguration lifecycle when Gate
  Controller properties change.
- Apply changed input devices, state selections, polarities, and timing values
  immediately after the device configuration is saved, without requiring a
  plugin restart.

## 0.1.0-alpha.5 — 2026-09-09

- Make the native Garage Controller state follow Indigo's established
  convention: on when closed and off in every other gate state.
- Give that native state the textual gate-state UI value as a fallback for
  Indigo views that render it instead of the configured `position` state.
- Refresh device-state and display-state metadata when communication starts.
- Preserve the observed gate state when sending a momentary control pulse.

## 0.1.0-alpha.4 — 2026-09-09

- Make the Indigo device display state an explicit textual gate state rather
  than an enumerated value that could initially appear as numeric zero.
- Clarify that the momentary control selection is the Indigo output physically
  wired to the GiBiDi controller's command/pushbutton input.

## 0.1.0-alpha.3 — 2026-09-09

- Make direct publication of the new Gate Controller device through HomeKitLink
  Siri the selected migration path.
- Remove the temporary Variable Mirror/`GateMotion` compatibility output.
- Add the exact **Front Gate** publication settings and accessory-replacement
  checklist.

## 0.1.0-alpha.2 — 2026-09-09

- Preserve the Variable Mirror/HomeKitLink Siri command convention by keeping
  `onOffState` momentary and using `doorState` exclusively for position.
- Add an optional state-transition mirror to an existing Indigo variable.
- Document the identity-preserving migration for the existing **Front Gate**
  HomeKit accessory and legacy variable-change announcements.

## 0.1.0-alpha.1 — 2026-09-09

- Initial standalone Indigo Gate Controller plugin.
- Configurable primary and optional gate inputs.
- Flash-rate motion classification and physical-limit authority.
- HomeKit-compatible garage-door state and standard control pulse.
- Transition events, optional Action Group hooks, and open-too-long timer.
- Deduplicated input failure and recovery reporting.
- Staged migration and credential-remediation documentation.
