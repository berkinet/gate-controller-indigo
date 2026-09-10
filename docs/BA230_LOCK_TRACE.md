# BA230 lock-output observations

This note records observations made on 10 September 2026 while monitoring the
GiBiDi BA230 `Lock1` and `Lock2` (`EL1` and `EL2`) outputs. It documents the
installed gate only; it is not a general specification for every BA230 firmware
revision or configuration.

## Test arrangement

- `EL1` and `EL2` were connected only to channels 8 and 9 of a Phidgets
  DAQ1301_0 digital-input device, serial 592034, on VINT hub port 1.
- No electric locks, coils, relays, or other loads were connected to these
  outputs during the test.
- Phidgets22 plugin 0.3.53 logged every raw Digital Input state-change callback
  before Indigo state processing.
- Existing Indigo triggers had previously shown large numbers of alternating
  changes. Raw callback logging was added to distinguish activity delivered by
  the Phidget API from duplication in Indigo triggers or device-state updates.

The BA230 documentation describes a nominal +12 V DC lock pulse. The electrical
waveform at the terminals has not yet been verified with an oscilloscope; a
Pokit meter may be used for that follow-up measurement.

## Raw callback results

One complete automatic open-and-close cycle produced four activation envelopes:

| Phase | Channel | Start | End | Duration | Callbacks |
| --- | --- | --- | --- | ---: | ---: |
| Opening | Lock1 | 20:54:42.628 | 20:54:45.715 | 3.087 s | 492 |
| Opening | Lock2 | 20:54:47.806 | 20:54:50.883 | 3.077 s | 524 |
| Closing | Lock2 | 20:55:34.825 | 20:55:37.911 | 3.086 s | 490 |
| Closing | Lock1 | 20:55:39.985 | 20:55:43.069 | 3.084 s | 486 |

Within each envelope, callbacks alternated perfectly between true and false.
There were no repeated consecutive states and no missing plugin sequence
numbers. The median interval between callback timestamps was about 4 ms, with
some callbacks sharing a millisecond timestamp and occasional larger gaps.
Consequently, the API trace proves that Indigo receives rapid alternating raw
states, but network delivery and logging timestamps are not suitable for an
exact electrical-frequency measurement.

The activation envelopes lasted approximately 3.08 seconds. Their start-to-start
separation was approximately 5.17 seconds during opening and 5.16 seconds during
closing.

## Relationship to SPIA and position limits

A separate cycle with detailed Gate Controller logging provided the following
alignment. The configured position inputs monitor the first leaf.

### Opening

| Event | Time | Relationship |
| --- | --- | --- |
| SPIA first active edge | 19:23:51.211 | Start of controller activity |
| Lock1 envelope starts | 19:23:51.609 | 0.398 s after SPIA |
| Closed limit releases | 19:23:54.128 | 2.519 s after Lock1 starts |
| Lock1 envelope ends | 19:23:54.682 | 0.554 s after limit release |
| Lock2 envelope starts | 19:23:56.776 | 5.167 s after Lock1 starts |
| Lock2 envelope ends | 19:23:59.853 | — |
| Open limit activates | 19:24:10.158 | 10.305 s after Lock2 ends |
| Estimated second leaf completes | 19:24:13.711 | Gate reports Open |

### Closing

| Event | Time | Relationship |
| --- | --- | --- |
| Lock2 envelope starts | 19:24:43.799 | Closing SPIA flashing resumes at approximately the same time |
| Lock2 envelope ends | 19:24:46.875 | — |
| Lock1 envelope starts | 19:24:48.958 | 5.159 s after Lock2 starts |
| Open limit releases | 19:24:51.506 | 2.548 s after Lock1 starts |
| Lock1 envelope ends | 19:24:52.031 | 0.525 s after limit release |
| Closed limit activates | 19:25:07.340 | Gate reports Closed |
| SPIA final inactive edge | 19:25:15.182 | 7.842 s after closed detection |

The approximately 7.8-second post-limit SPIA interval is one observation, not a
configured expectation. More cycles are required before assigning a normal
range or diagnostic timeout.

## Corrected sequence chart

The combined observed and inferred sequence is:

```text
OPENING

Known Closed
    ↓
SPIA activity begins
    ↓  0.398 s observed
Lock1 envelope starts ─────────────┐
    ↓  2.519 s                    │ first-leaf controller phase
Closed limit releases             │ physical movement confirmed
    ↓  0.554 s                    │
Lock1 envelope ends ──────────────┘
    ↓  2.094 s
Lock2 envelope starts
    ↓  3.077 s
Lock2 envelope ends
    ↓  10.305 s
Open limit activates
    ↓  3.553 s configured estimate in this test
Estimated second leaf completes
    ↓
Gate reports Open


CLOSING

Known Open / held open
    ↓
Lock2 envelope starts ≈ fast SPIA flashing resumes
    ↓  3.076 s
Lock2 envelope ends
    ↓  2.083 s
Lock1 envelope starts ─────────────┐
    ↓  2.548 s                    │ first-leaf controller phase
Open limit releases               │ physical movement confirmed
    ↓  0.525 s                    │
Lock1 envelope ends ──────────────┘
    ↓  15.309 s
Closed limit activates
    ↓
Gate reports Closed
    ↓  7.842 s observed
Fast SPIA flashing ends
    ↓
BA230 closing cycle complete / idle
```

Slow SPIA classification belongs near the beginning of opening and, like
Lock1, precedes release of the closed limit by roughly three seconds. Its exact
placement is classifier-dependent because the plugin must observe enough SPIA
edges to distinguish the slow and fast rates.

## Supported interpretation

The observations support treating Lock1 and Lock2 as short controller-sequence
envelopes rather than persistent locked/unlocked states:

- Lock1 is strongly associated with the first monitored leaf. In both
  directions, its endpoint limit released about 2.5 seconds after the Lock1
  envelope began.
- Lock2 is consistent with the delayed second leaf.
- Lock1 followed by Lock2 is consistent with opening choreography.
- Lock2 followed by Lock1 is consistent with closing choreography.
- When the gate is known closed, Lock1 is an early indication that the BA230
  has initiated opening. It does not by itself prove physical movement.
- Slow SPIA classification and Lock1 both precede release of the closed limit
  by roughly three seconds and can corroborate one another.
- The position-limit release is the evidence that physical movement actually
  began. A final endpoint limit remains authoritative for physical position.
- The end of fast SPIA flashing follows closed detection and indicates that the
  BA230 operating sequence has finished, which is distinct from detecting the
  closed position itself.

The rapid transitions and their exact count have no demonstrated semantic
meaning. Only the envelope channel, order, start, duration, and relationships to
SPIA and the physical limits are potentially useful.

## Current design decision

No operational state-machine change is justified by this single test session.
The Gate Controller is not intended to tightly synchronize people or vehicles
with gate movement, and users must visually confirm that passage is safe.

Lock inputs therefore remain optional diagnostic states:

- They do not determine gate position or command the gate.
- Their individual transitions remain absent from ordinary Debugging output
  because they are excessively noisy.
- Detailed debugging may expose them when specifically required.
- A future optional diagnostic layer could collapse transitions into envelopes
  and report only significant inconsistencies, such as an expected limit not
  releasing after the controller sequence begins. Such diagnostics must remain
  advisory and require timing measurements from several normal cycles first.
