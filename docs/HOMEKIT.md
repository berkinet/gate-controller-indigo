# Preserving the HomeKitLink Siri interface

The existing gate is not published directly from the old motion script. Indigo
device **Virtual Front Gate** is the HomeKitLink Siri boundary:

- HomeKit name: **Front Gate**
- HomeKitLink subtype: **GarageDoor**
- Source state: **doorState**
- Motion support: enabled
- Published: enabled
- Bridge unique ID: `583879`
- State source: Variable Mirror reads the `GateMotion` Indigo variable
- Command path: Variable Mirror pulses `House - gate control`

These are observed migration facts, not values hard-coded into Gate Controller.

## State and message contract

Gate Controller publishes the same numeric `doorState` contract used by the
current Variable Mirror facade:

| Gate state | `doorState` | HomeKitLink behavior |
| --- | ---: | --- |
| open | 0 | Open |
| closed | 1 | Closed; clears obstruction |
| opening | 2 | Opening, target open |
| closing | 3 | Closing, target closed |
| stopped, unknown, fault, paused | 4 | Existing stopped/obstructed presentation |

HomeKitLink translates an open target into Indigo **Turn Off** and a closed
target into Indigo **Turn On**. The Gate Controller relay interface accepts
Turn On, Turn Off, and Toggle as the same physical momentary command, matching
the single-button GiBiDi controller. Its `onOffState` remains a momentary
command surface and is reset to Off; gate position is carried only by
`doorState` and `position`.

## Identity-preserving migration (recommended)

HomeKitLink derives the HomeKit accessory ID partly from the Indigo device ID.
Publishing a newly created Gate Controller device therefore creates a different
HomeKit accessory even when it has the same name. Home scenes and automations
may then reference the old accessory.

To preserve the existing accessory identity and Siri/Home messaging:

1. Keep **Virtual Front Gate** published to HomeKitLink with its existing name,
   subtype, bridge, source state, and motion setting.
2. Validate Gate Controller in observer mode without a compatibility variable.
3. In one controlled cutover, disable the old `gate_motion.py` writer and select
   `GateMotion` in Gate Controller's **Mirror transitions to variable** field.
4. Leave Variable Mirror pointed at `GateMotion`. It will continue converting
   the exact strings into `doorState`, so the existing HomeKit accessory ID and
   messaging remain unchanged.
5. Initially leave the Variable Mirror command path pointed directly at
   `House - gate control`. If all commands must later pass through Gate
   Controller, use one Indigo Action Group containing **Pulse gate control**;
   configure Variable Mirror to execute that Action Group. Do not point its
   timed pulse directly at the Gate Controller relay, because the timed Turn
   Off would otherwise be a second gate command.
6. Test “open Front Gate” and “close Front Gate,” plus Home app status during a
   complete open, close, and interrupted/stopped cycle.

Gate Controller deliberately does not write the compatibility variable during
plugin startup. That avoids replaying existing variable-change announcements,
lighting actions, or other legacy triggers after an Indigo restart.

## Direct publication later

The Gate Controller device can be published directly as a HomeKitLink
`GarageDoor` using `doorState`, motion enabled, and the HomeKit name **Front
Gate**. This removes the Variable Mirror facade, but HomeKit will see a new
accessory because its Indigo device ID is different. Use that route only during
an intentional Home migration where affected scenes and automations can be
repaired.
