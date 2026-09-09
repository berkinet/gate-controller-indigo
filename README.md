# Gate Controller for Indigo

Gate Controller replaces a collection of Indigo scripts, variables, triggers,
and timers with one configurable virtual gate device. It observes the gate
controller's flashing-lamp signal, combines that with physical open and closed
limits, and publishes a single authoritative gate state.

This is an alpha release. Install and exercise it alongside the existing gate
automation before disabling anything that currently controls or monitors the
gate.

## What the alpha provides

- Configurable Indigo device/state/polarity mappings for the flashing lamp,
  fully-open detector, and fully-closed detector.
- Optional second-leaf open and closed limits. When present, both leaves must
  reach the corresponding limit before the entire gate reports open or closed.
- Optional safety, active-cycle, and lock inputs exposed as diagnostic states.
- Pulse-rate classification using the existing GiBiDi behavior: approximately
  0.8 seconds means closing and 1.6 seconds means opening by default.
- Physical limits that always override inferred motion; simultaneous opposing
  limits produce a fault.
- A Garage Controller relay device with HomeKit-compatible `doorState` values:
  open 0, closed 1, opening 2, closing 3, and stopped/unknown/fault 4.
- Transition triggers for opening, closing, open, closed, stopped, unknown,
  paused, fault, and open-too-long.
- Optional Action Group hooks for straightforward migration.
- A safe momentary control action using Indigo's server-managed pulse duration.
- Deduplicated source-input errors with explicit recovery reporting.

Plugin startup synchronizes current input levels without counting an already-on
lamp as a pulse and without emitting transition triggers or Action Groups. This
prevents restarts from replaying announcements and lighting actions.

## Install for alpha testing

1. Download or clone the repository on the Indigo server Mac.
2. Double-click `Gate Controller.indigoPlugin` and let Indigo install it.
3. Create a **Gate Controller** device.
4. Map the flashing-lamp, fully-open, and fully-closed Indigo device states.
5. Confirm the active polarity of each input before configuring control output.
6. Observe a complete open and close cycle and verify `position`, `doorState`,
   input states, and `lampInterval`.
7. Add transition triggers for announcements and lighting only after state
   detection has been verified.

Do not disable the existing safety or gate-control automation during initial
testing. The plugin never directly drives motors; its optional control action
only pulses the already-existing gate input device.

## Automation boundary

The plugin owns reusable gate behavior: sensing, pulse classification, state,
faults, timers, transition events, and the momentary control pulse. Site-specific
effects such as spoken announcements, exterior lighting, email, or camera
captures should remain ordinary Indigo trigger actions listening to plugin
events. This keeps the gate model testable without hiding house-specific policy
inside Python.

See [docs/MIGRATION.md](docs/MIGRATION.md) for the staged cutover and
[SECURITY.md](SECURITY.md) for the credential cleanup identified during the
existing-automation review.

## Development

The state classifier is independent of Indigo and uses the Python standard
library only.

```shell
python3 -m unittest discover -s tests -v
```

## License

MIT
