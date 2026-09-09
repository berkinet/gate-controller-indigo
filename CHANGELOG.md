# Changelog

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
