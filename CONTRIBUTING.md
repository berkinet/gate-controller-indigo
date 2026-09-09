# Contributing

Contributions to Gate Controller are welcome. Keep changes small, testable, and
independent of a particular household's Indigo configuration.

## Development environment

The plugin targets the Python 3 runtime embedded in current Indigo releases.
The test suite uses only the standard library; coverage reporting additionally
requires [`coverage`](https://coverage.readthedocs.io/).

Run the tests before submitting a change:

```sh
python3 -m unittest discover -s tests -v
```

To inspect branch coverage locally:

```sh
python3 -m pip install coverage==7.10.6
coverage run -m unittest discover -s tests -v
coverage report
```

## Architecture and tests

- Keep motion classification and transition rules in `gate_state.py`, which
  must remain independent of Indigo.
- Keep Indigo lifecycle, device I/O, timers, actions, and events in `plugin.py`.
- Add state-machine tests for classification changes and mocked-runtime tests
  for Indigo-facing behavior.
- Update the manifest tests when adding callbacks, events, states, or settings.
- Preserve physical limit switches as authoritative over inferred or forced
  motion state.

## Pull-request checklist

- The complete unit suite passes.
- New behavior and failure paths have focused tests.
- XML callbacks and event identifiers agree with `plugin.py`.
- User-visible behavior is documented in `README.md` or the relevant guide.
- `CHANGELOG.md` describes the change under **Unreleased**.
- No passwords, tokens, camera URLs, Indigo databases, exported triggers, or
  other site-specific data are included.

Version numbers and release archives are updated only as part of a coordinated
release. See `SECURITY.md` before sharing logs, configurations, or automation
exports.
