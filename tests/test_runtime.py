import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[1]
SERVER = ROOT / "Gate Controller.indigoPlugin" / "Contents" / "Server Plugin"


class FakeLogger:
    def __init__(self):
        self.records = []
        self.level = None

    def _record(self, level, message, *args):
        self.records.append((level, message % args if args else message))

    def setLevel(self, level):
        self.level = level

    def debug(self, message, *args):
        self._record("debug", message, *args)

    def log(self, level, message, *args):
        self._record("detailed" if level == 5 else str(level), message, *args)

    def info(self, message, *args):
        self._record("info", message, *args)

    def warning(self, message, *args):
        self._record("warning", message, *args)

    def error(self, message, *args):
        self._record("error", message, *args)


class FakeDevice:
    def __init__(self, device_id, name, states=None, props=None, enabled=True):
        self.id = device_id
        self.name = name
        self.states = dict(states or {})
        self.pluginProps = dict(props or {})
        self.enabled = enabled
        self.error = None
        self.ui_values = {}
        self.display_metadata_refreshes = 0
        self.state_image = None
        self.supportsOnState = "onOffState" in self.states

    def updateStateOnServer(self, key, value=None, **kwargs):
        self.states[key] = value
        if "uiValue" in kwargs:
            self.ui_values[key] = kwargs["uiValue"]

    def updateStatesOnServer(self, updates):
        for update in updates:
            self.states[update["key"]] = update["value"]
            if "uiValue" in update:
                self.ui_values[update["key"]] = update["uiValue"]

    def setErrorStateOnServer(self, value):
        self.error = value

    def stateListOrDisplayStateIdChanged(self):
        self.display_metadata_refreshes += 1

    def updateStateImageOnServer(self, image):
        self.state_image = image


class FakeDevices(dict):
    def __iter__(self):
        return iter(self.values())

    def iter(self, _filter):
        return iter(self.values())

    def subscribeToChanges(self):
        pass


class RuntimePlugin:
    def __init__(self):
        self.logger = FakeLogger()
        self.events = []
        self.groups = []

    def emit(self, device, event_id):
        self.events.append((device.id, event_id))

    def run_action_group(self, device, property_name):
        self.groups.append((device.id, property_name))


def base_props():
    return {
        "lampDeviceId": "1", "lampStateId": "onOffState",
        "lampActiveWhen": "true",
        "openDeviceId": "2", "openStateId": "onOffState",
        "openActiveWhen": "true",
        "closedDeviceId": "3", "closedStateId": "onOffState",
        "closedActiveWhen": "true",
        "debounceSeconds": "0.1", "idleTimeoutSeconds": "2.5",
        "closingInterval": "0.8", "openingInterval": "1.6",
        "intervalBand": "0.1", "openTooLongSeconds": "1800",
        "inputErrorReminderSeconds": "3600",
    }


fake_indigo = types.ModuleType("indigo")
fake_indigo.devices = FakeDevices()
fake_indigo.actionGroups = []
fake_indigo.Dict = dict
fake_indigo.kDeviceAction = types.SimpleNamespace(TurnOn=1, TurnOff=2, Toggle=3)
fake_indigo.kStateImageSel = types.SimpleNamespace(Locked=1, Unlocked=2)
fake_indigo.trigger = types.SimpleNamespace(execute=lambda _trigger_id: None)
fake_indigo.actionGroup = types.SimpleNamespace(execute=lambda _group_id: None)
fake_indigo.device = types.SimpleNamespace(
    turnOn=lambda *args, **kwargs: None,
    turnOff=lambda *args, **kwargs: None)


class FakeHandler:
    def __init__(self):
        self.level = None

    def setLevel(self, level):
        self.level = level


class FakePluginBase:
    def __init__(self, *_args):
        self.logger = FakeLogger()
        self.indigo_log_handler = FakeHandler()
        self.plugin_file_handler = FakeHandler()
        self.base_device_updates = []

    def deviceUpdated(self, original, updated):
        self.base_device_updates.append((original, updated))


fake_indigo.PluginBase = FakePluginBase
sys.modules["indigo"] = fake_indigo
sys.path.insert(0, str(SERVER))
SPEC = importlib.util.spec_from_file_location("gate_plugin_test", SERVER / "plugin.py")
gate_plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate_plugin)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        fake_indigo.devices.clear()
        fake_indigo.devices.update({
            1: FakeDevice(1, "Lamp", {"onOffState": False}),
            2: FakeDevice(2, "Open Limit", {"onOffState": False}),
            3: FakeDevice(3, "Closed Limit", {"onOffState": True}),
        })

    def test_startup_synchronizes_closed_without_events_or_hooks(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        self.assertEqual("closed", gate.states["position"])
        self.assertEqual("Closed", gate.ui_values["position"])
        self.assertEqual(1, gate.states["doorState"])
        self.assertTrue(gate.states["onOffState"])
        self.assertEqual("Closed", gate.ui_values["onOffState"])
        self.assertEqual(fake_indigo.kStateImageSel.Locked, gate.state_image)
        self.assertTrue(gate.states["inputsAvailable"])
        self.assertEqual([], owner.events)
        self.assertEqual([], owner.groups)
        self.assertEqual([], [message for level, message in owner.logger.records
                              if level == "info"])

    def test_startup_overwrites_a_legacy_numeric_display_with_unknown(self):
        owner = RuntimePlugin()
        fake_indigo.devices[3].states["onOffState"] = False
        gate = FakeDevice(
            100, "Main Gate", states={"position": 0}, props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        self.assertEqual("unknown", gate.states["position"])
        self.assertEqual("Unknown", gate.ui_values["position"])
        self.assertEqual(4, gate.states["doorState"])
        self.assertEqual(fake_indigo.kStateImageSel.Unlocked, gate.state_image)

    def test_second_leaf_must_also_reach_limit(self):
        props = base_props()
        props.update({"delayAfterFirstLeaf": "false",
                      "open2DeviceId": "4", "open2StateId": "onOffState",
                      "open2ActiveWhen": "true"})
        fake_indigo.devices[2].states["onOffState"] = True
        fake_indigo.devices[3].states["onOffState"] = False
        fake_indigo.devices[4] = FakeDevice(
            4, "Second Open Limit", {"onOffState": False})
        runtime = gate_plugin.GateRuntime(
            RuntimePlugin(), FakeDevice(100, "Main Gate", props=props))
        _values, open_active, closed_active = runtime._read_inputs()
        self.assertFalse(open_active)
        self.assertFalse(closed_active)
        fake_indigo.devices[4].states["onOffState"] = True
        _values, open_active, _closed_active = runtime._read_inputs()
        self.assertTrue(open_active)

    def test_first_leaf_endpoint_is_published_after_configured_delay(self):
        owner = RuntimePlugin()
        props = base_props()
        props.update({"delayAfterFirstLeaf": "true",
                      "secondLeafOpeningDelaySeconds": "60",
                      "secondLeafClosingDelaySeconds": "0"})
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()

        fake_indigo.devices[3].states["onOffState"] = False
        runtime.evaluate("closed limit released")
        self.assertEqual("opening", gate.states["position"])
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate("lamp rising")
        self.assertEqual("opening", gate.states["position"])
        fake_indigo.devices[2].states["onOffState"] = True
        runtime.evaluate("open limit reached")

        self.assertEqual("opening", gate.states["position"])
        self.assertEqual("open", runtime._pending_endpoint)
        self.assertNotIn((100, "open"), owner.events)
        runtime._endpoint_timer.cancel()
        runtime._endpoint_delay_fired(runtime._generation)
        self.assertEqual("open", gate.states["position"])
        self.assertIn((100, "open"), owner.events)

    def test_first_leaf_delay_is_canceled_when_limit_releases(self):
        owner = RuntimePlugin()
        props = base_props()
        props.update({"delayAfterFirstLeaf": "true",
                      "secondLeafOpeningDelaySeconds": "60",
                      "secondLeafClosingDelaySeconds": "0"})
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        fake_indigo.devices[3].states["onOffState"] = False
        runtime.evaluate()
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate()
        fake_indigo.devices[2].states["onOffState"] = True
        runtime.evaluate()
        self.assertEqual("open", runtime._pending_endpoint)

        fake_indigo.devices[2].states["onOffState"] = False
        runtime.evaluate("open limit released")
        self.assertIsNone(runtime._pending_endpoint)
        self.assertEqual("closing", gate.states["position"])

    def test_zero_closing_delay_publishes_closed_immediately(self):
        owner = RuntimePlugin()
        props = base_props()
        props.update({"delayAfterFirstLeaf": "true",
                      "secondLeafOpeningDelaySeconds": "10",
                      "secondLeafClosingDelaySeconds": "0"})
        fake_indigo.devices[2].states["onOffState"] = True
        fake_indigo.devices[3].states["onOffState"] = False
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        fake_indigo.devices[2].states["onOffState"] = False
        runtime.evaluate("open limit released")
        self.assertEqual("closing", gate.states["position"])
        fake_indigo.devices[3].states["onOffState"] = True
        runtime.evaluate("closed limit reached")
        self.assertEqual("closed", gate.states["position"])
        self.assertIsNone(runtime._pending_endpoint)

    def test_nonzero_closing_delay_defers_closed(self):
        owner = RuntimePlugin()
        props = base_props()
        props.update({"delayAfterFirstLeaf": "true",
                      "secondLeafOpeningDelaySeconds": "10",
                      "secondLeafClosingDelaySeconds": "60"})
        fake_indigo.devices[2].states["onOffState"] = True
        fake_indigo.devices[3].states["onOffState"] = False
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        fake_indigo.devices[2].states["onOffState"] = False
        runtime.evaluate("open limit released")
        fake_indigo.devices[3].states["onOffState"] = True
        runtime.evaluate("closed limit reached")
        self.assertEqual("closing", gate.states["position"])
        self.assertEqual("closed", runtime._pending_endpoint)
        runtime._endpoint_timer.cancel()

    def test_identical_input_failure_is_suppressed_until_recovery(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        fake_indigo.devices[1].enabled = False
        runtime.evaluate()
        runtime.evaluate()
        warnings = [record for record in owner.logger.records
                    if record[0] == "warning"]
        self.assertEqual(1, len(warnings))
        self.assertFalse(gate.states["inputsAvailable"])
        fake_indigo.devices[1].enabled = True
        runtime.evaluate()
        self.assertTrue(gate.states["inputsAvailable"])
        self.assertIsNone(gate.error)
        self.assertTrue(any("recovered" in message for level, message
                            in owner.logger.records if level == "detailed"))

    def test_plugin_coalesces_input_recovery_and_synchronizes_silently(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        plugin.emit = mock.Mock()
        plugin.run_action_group = mock.Mock()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        fake_indigo.devices[1].states.clear()
        plugin.deviceStartComm(gate)
        runtime = plugin.runtimes[gate.id]
        self.assertTrue(runtime.recovering_inputs())

        timers = []

        class FakeTimer:
            def __init__(self, delay, callback, args):
                self.delay = delay
                self.callback = callback
                self.args = args
                self.cancelled = False
                timers.append(self)

            def start(self):
                pass

            def cancel(self):
                self.cancelled = True

        original = FakeDevice(1, "Lamp", {})
        fake_indigo.devices[1].states["onOffState"] = False
        updated = fake_indigo.devices[1]
        with mock.patch.object(gate_plugin.threading, "Timer", FakeTimer):
            plugin.deviceUpdated(original, updated)
            plugin.deviceUpdated(original, updated)
            self.assertEqual(2, len(timers))
            self.assertTrue(timers[0].cancelled)
            timers[-1].callback(*timers[-1].args)

        self.assertFalse(runtime.recovering_inputs())
        self.assertEqual("closed", runtime.machine.state)
        plugin.emit.assert_not_called()
        plugin.run_action_group.assert_not_called()
        info = [message for level, message in plugin.logger.records
                if level == "info"]
        self.assertEqual([], info)

    def test_only_opening_and_closed_are_routine_information(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()

        fake_indigo.devices[3].states["onOffState"] = False
        runtime.evaluate("closed limit released")
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate("lamp rising")
        fake_indigo.devices[1].states["onOffState"] = False
        runtime.evaluate("lamp falling")
        fake_indigo.devices[3].states["onOffState"] = True
        runtime.evaluate("closed limit reached")
        runtime.stop()

        self.assertEqual(
            ["Gate opening", "Gate closed."],
            [message for level, message in owner.logger.records
             if level == "info"])
        debug_messages = [message for level, message in owner.logger.records
                          if level == "debug"]
        detailed_messages = [message for level, message in owner.logger.records
                             if level == "detailed"]
        self.assertTrue(any("SPIA: on" in message
                            for message in debug_messages))
        self.assertTrue(any("lamp pulse accepted" in message
                            for message in detailed_messages))
        self.assertTrue(any("state changed" in message
                            for message in detailed_messages))

    def test_debug_input_timeline_excludes_lock_edges(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        values = {name: None for name in runtime.INPUTS}
        values.update({"lamp": False, "open": False, "closed": True,
                       "lock1": False, "lock2": False})
        runtime._publish_inputs(values, log_changes=False)
        owner.logger.records.clear()

        values.update({"lamp": True, "lock1": True, "lock2": True})
        runtime._publish_inputs(values)

        debug_messages = [message for level, message in owner.logger.records
                          if level == "debug"]
        self.assertEqual(["SPIA: on"], debug_messages)
        self.assertTrue(gate.states["lock1Active"])
        self.assertTrue(gate.states["lock2Active"])

    def test_force_cannot_override_an_active_physical_limit(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        runtime.force("open", pause_seconds=30)
        self.assertEqual("closed", runtime.machine.state)
        self.assertEqual("closed", gate.states["position"])

    def test_status_indicator_flashes_during_motion_and_stays_on_when_open(self):
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, suppressLogging: calls.append(
                ("on", device_id, suppressLogging)),
            turnOff=lambda device_id, suppressLogging: calls.append(
                ("off", device_id, suppressLogging)))
        fake_indigo.devices[4] = FakeDevice(
            4, "Kitchen Gate LED", {"onOffState": False})
        props = base_props()
        props["indicatorDeviceId"] = "4"
        runtime = gate_plugin.GateRuntime(
            RuntimePlugin(), FakeDevice(100, "Main Gate", props=props))

        runtime.start()
        fake_indigo.devices[3].states["onOffState"] = False
        runtime.evaluate("closed limit released")
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate("lamp rising")
        fake_indigo.devices[1].states["onOffState"] = False
        runtime.evaluate("lamp falling")
        fake_indigo.devices[2].states["onOffState"] = True
        runtime.evaluate("open limit reached")
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate("lamp changed while open")
        fake_indigo.devices[1].states["onOffState"] = False
        runtime.evaluate("lamp changed again while open")
        runtime.stop()

        self.assertEqual(
            [("off", 4, True), ("on", 4, True),
             ("off", 4, True), ("on", 4, True)], calls)

    def test_status_indicator_stays_on_for_forced_locked_open_state(self):
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, **_kwargs: calls.append(("on", device_id)),
            turnOff=lambda device_id, **_kwargs: calls.append(("off", device_id)))
        fake_indigo.devices[2].states["onOffState"] = False
        fake_indigo.devices[3].states["onOffState"] = False
        fake_indigo.devices[4] = FakeDevice(
            4, "Kitchen Gate LED", {"onOffState": False})
        props = base_props()
        props["indicatorDeviceId"] = "4"
        runtime = gate_plugin.GateRuntime(
            RuntimePlugin(), FakeDevice(100, "Main Gate", props=props))

        runtime.start()
        runtime.force("open", pause_seconds=3600)
        fake_indigo.devices[1].states["onOffState"] = True
        runtime.evaluate("lamp rising while locked open")
        fake_indigo.devices[1].states["onOffState"] = False
        runtime.evaluate("lamp falling while locked open")
        runtime.stop()

        self.assertEqual([("off", 4), ("on", 4)], calls)

    def test_status_indicator_output_can_be_inverted(self):
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, **_kwargs: calls.append(("on", device_id)),
            turnOff=lambda device_id, **_kwargs: calls.append(("off", device_id)))
        fake_indigo.devices[4] = FakeDevice(
            4, "Kitchen Gate LED", {"onOffState": False})
        props = base_props()
        props.update({"indicatorDeviceId": "4", "indicatorInverted": "true"})
        runtime = gate_plugin.GateRuntime(
            RuntimePlugin(), FakeDevice(100, "Main Gate", props=props))
        runtime.start()
        runtime.stop()
        self.assertEqual([("on", 4)], calls)

    def test_status_indicator_failure_is_deduplicated_and_nonfatal(self):
        def fail(_device_id, **_kwargs):
            raise RuntimeError("output detached")

        fake_indigo.device = types.SimpleNamespace(
            turnOn=fail, turnOff=lambda _device_id, **_kwargs: None)
        fake_indigo.devices[2].states["onOffState"] = False
        fake_indigo.devices[3].states["onOffState"] = False
        fake_indigo.devices[4] = FakeDevice(
            4, "Kitchen Gate LED", {"onOffState": False})
        props = base_props()
        props["indicatorDeviceId"] = "4"
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        runtime.force("open")
        runtime.force("open")
        runtime.stop()

        self.assertEqual("open", gate.states["position"])
        warnings = [message for level, message in owner.logger.records
                    if level == "warning" and "indicator" in message]
        self.assertEqual(1, len(warnings))

    def test_control_uses_indigo_server_managed_duration(self):
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, duration: calls.append((device_id, duration)))
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        gate = FakeDevice(100, "Main Gate", props={
            "controlDeviceId": "44", "controlPulseSeconds": "1"},
            states={"onOffState": True, "position": "closed"})
        plugin.pulseGate(None, gate)
        self.assertEqual([(44, 1)], calls)
        self.assertTrue(gate.states["onOffState"])
        self.assertEqual("closed", gate.states["position"])

    def test_logging_preference_supports_debug_and_detailed_debug(self):
        plugin = gate_plugin.Plugin(
            "id", "name", "version", {"loggingLevel": "30"})
        self.assertEqual(30, plugin.log_level)
        self.assertEqual(5, plugin.logger.level)
        self.assertEqual(30, plugin.indigo_log_handler.level)
        self.assertEqual(30, plugin.plugin_file_handler.level)

        plugin.closedPrefsConfigUi({"loggingLevel": "10"}, False)
        self.assertEqual(10, plugin.log_level)
        self.assertEqual(10, plugin.indigo_log_handler.level)

        plugin.closedPrefsConfigUi({"loggingLevel": "5"}, False)
        self.assertEqual(5, plugin.log_level)
        self.assertEqual(5, plugin.indigo_log_handler.level)

    def test_fractional_control_duration_is_rejected_without_raw_exception(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, duration: calls.append((device_id, duration)))
        gate = FakeDevice(100, "Main Gate", props={
            "controlDeviceId": "44", "controlPulseSeconds": "0.75"})
        plugin.pulseGate(None, gate)
        self.assertEqual([], calls)
        errors = [message for level, message in plugin.logger.records
                  if level == "error"]
        self.assertEqual(1, len(errors))
        self.assertIn("whole number", errors[0])

    def test_device_start_refreshes_indigo_display_metadata(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        gate = FakeDevice(100, "Main Gate", props=base_props())
        plugin.deviceStartComm(gate)
        self.assertEqual(1, gate.display_metadata_refreshes)

    def test_device_updates_delegate_to_indigo_reconfiguration_lifecycle(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        original = FakeDevice(100, "Main Gate", props=base_props())
        updated_props = base_props()
        updated_props.update({"openDeviceId": "3", "closedDeviceId": "2"})
        updated = FakeDevice(100, "Main Gate", props=updated_props)
        plugin.deviceUpdated(original, updated)
        self.assertEqual([(original, updated)], plugin.base_device_updates)

    def test_homekit_door_state_contract_matches_homekitlink(self):
        self.assertEqual({
            "open": 0, "closed": 1, "opening": 2, "closing": 3,
            "stopped": 4, "unknown": 4, "fault": 4, "paused": 4,
        }, gate_plugin.DOOR_STATE)

    def test_homekit_open_and_close_commands_both_use_momentary_control(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        calls = []
        plugin.pulseGate = lambda action, device: calls.append(
            (action.deviceAction, device.id))
        gate = FakeDevice(100, "Main Gate")
        for device_action in (fake_indigo.kDeviceAction.TurnOff,
                              fake_indigo.kDeviceAction.TurnOn,
                              fake_indigo.kDeviceAction.Toggle):
            plugin.actionControlDevice(
                types.SimpleNamespace(deviceAction=device_action), gate)
        self.assertEqual([(2, 100), (1, 100), (3, 100)], calls)

    def test_indicator_cannot_reuse_a_gate_input_or_control_device(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        props = base_props()
        props["indicatorDeviceId"] = props["lampDeviceId"]
        valid, _values, errors = plugin.validateDeviceConfigUi(
            props, "gateController", 100)
        self.assertFalse(valid)
        self.assertIn("gate input or control", errors["indicatorDeviceId"])

    def test_source_lookup_classifies_form_selection_errors(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})

        cases = (
            ({"lampDeviceId": "bad", "lampStateId": "onOffState"},
             "invalid"),
            ({"lampDeviceId": "0", "lampStateId": "onOffState"},
             "missing"),
            ({"lampDeviceId": "99", "lampStateId": "onOffState"},
             "unavailable"),
            ({"lampDeviceId": "1", "lampStateId": "missingState"},
             "state"),
            ({"lampDeviceId": "1", "lampStateId": "onOffState"}, None),
        )
        for values, expected in cases:
            with self.subTest(expected=expected):
                _source, _source_id, _state_id, error = (
                    plugin._lookup_source(values, "lamp"))
                self.assertEqual(expected, error)

    def test_source_change_clears_only_stale_state_selections(self):
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        values = base_props()
        values.update({
            "open2DeviceId": "99", "open2StateId": "onOffState",
            "safety1DeviceId": "0", "safety1StateId": "oldState",
        })

        updated = plugin.sourceDeviceChanged(
            values, "gateController", 100)

        self.assertEqual("onOffState", updated["lampStateId"])
        self.assertEqual("", updated["open2StateId"])
        self.assertEqual("", updated["safety1StateId"])

if __name__ == "__main__":
    unittest.main()
