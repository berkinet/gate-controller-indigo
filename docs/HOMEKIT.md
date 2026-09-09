# Replacing the HomeKitLink Siri gate accessory

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

## Direct publication

HomeKitLink derives the HomeKit accessory ID partly from the Indigo device ID.
Publishing a newly created Gate Controller device therefore creates a different
HomeKit accessory even when it has the same name. Home scenes and automations
that reference **Virtual Front Gate** must be reassigned to the replacement.

The accepted migration replaces the old accessory while preserving its visible
interface and state semantics:

1. Create the plugin device with a descriptive Indigo name such as **GiBiDi
   Front Gate** and validate it in observer mode over complete open and close
   cycles.
2. Configure its momentary control device as `House - gate control` and perform
   one supervised Indigo pulse test.
3. Record the old accessory's room, favorites, notification settings, scenes,
   and Home automations before removing it.
4. In HomeKitLink Siri, stop publishing **Virtual Front Gate**.
5. Publish **GiBiDi Front Gate** on bridge `583879` using:

   - HomeKit name: **Front Gate**
   - subtype: **GarageDoor**
   - source state: **doorState**
   - motion support: enabled

6. Restart or refresh the HomeKitLink bridge as required, remove any stale old
   accessory from Home, and place the replacement in the previous room.
7. Reassign every scene and Home automation that referenced the old accessory,
   then restore favorite and notification settings.
8. Test “open Front Gate” and “close Front Gate,” plus Home status during a
   complete open, close, and interrupted/stopped cycle.

After this cutover, HomeKit status and commands use Gate Controller directly;
Variable Mirror and `GateMotion` are no longer part of the HomeKit path. Remove
them only after the Indigo announcement, lighting, alarm, and camera triggers
have also been migrated to Gate Controller transition events.
