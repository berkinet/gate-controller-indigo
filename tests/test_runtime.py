import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SERVER = ROOT / "Gate Controller.indigoPlugin" / "Contents" / "Server Plugin"


class FakeLogger:
    def __init__(self):
        self.records = []

    def _record(self, level, message, *args):
        self.records.append((level, message % args if args else message))

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

    def updateStateOnServer(self, key, value=None, **kwargs):
        self.states[key] = value

    def updateStatesOnServer(self, updates):
        for update in updates:
            self.states[update["key"]] = update["value"]

    def setErrorStateOnServer(self, value):
        self.error = value


class FakeVariable:
    def __init__(self, variable_id, name, value):
        self.id = variable_id
        self.name = name
        self.value = value


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
fake_indigo.variables = FakeDevices()
fake_indigo.actionGroups = []
fake_indigo.Dict = dict
fake_indigo.kDeviceAction = types.SimpleNamespace(TurnOn=1, TurnOff=2, Toggle=3)
fake_indigo.trigger = types.SimpleNamespace(execute=lambda _trigger_id: None)
fake_indigo.actionGroup = types.SimpleNamespace(execute=lambda _group_id: None)
fake_indigo.device = types.SimpleNamespace(turnOn=lambda *args, **kwargs: None)


def update_variable(variable_id, value):
    fake_indigo.variables[variable_id].value = value


fake_indigo.variable = types.SimpleNamespace(updateValue=update_variable)


class FakePluginBase:
    def __init__(self, *_args):
        self.logger = FakeLogger()


fake_indigo.PluginBase = FakePluginBase
sys.modules["indigo"] = fake_indigo
sys.path.insert(0, str(SERVER))
SPEC = importlib.util.spec_from_file_location("gate_plugin_test", SERVER / "plugin.py")
gate_plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate_plugin)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        fake_indigo.devices.clear()
        fake_indigo.variables.clear()
        fake_indigo.devices.update({
            1: FakeDevice(1, "Lamp", {"onOffState": False}),
            2: FakeDevice(2, "Open Limit", {"onOffState": False}),
            3: FakeDevice(3, "Closed Limit", {"onOffState": True}),
        })

    def test_startup_synchronizes_closed_without_events_or_hooks(self):
        owner = gate_plugin.Plugin("id", "name", "version", {})
        owner.events = []
        owner.groups = []
        owner.emit = lambda device, event_id: owner.events.append(
            (device.id, event_id))
        owner.run_action_group = lambda device, property_name: owner.groups.append(
            (device.id, property_name))
        props = base_props()
        props["compatibilityVariableId"] = "7"
        fake_indigo.variables[7] = FakeVariable(7, "GateMotion", "legacy-value")
        gate = FakeDevice(100, "Main Gate", props=props)
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        self.assertEqual("closed", gate.states["position"])
        self.assertEqual(1, gate.states["doorState"])
        self.assertFalse(gate.states["onOffState"])
        self.assertTrue(gate.states["inputsAvailable"])
        self.assertEqual([], owner.events)
        self.assertEqual([], owner.groups)
        self.assertEqual("legacy-value", fake_indigo.variables[7].value)
        fake_indigo.devices[2].states["onOffState"] = True
        fake_indigo.devices[3].states["onOffState"] = False
        runtime.evaluate()
        self.assertEqual("open", fake_indigo.variables[7].value)

    def test_second_leaf_must_also_reach_limit(self):
        props = base_props()
        props.update({"open2DeviceId": "4", "open2StateId": "onOffState",
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
                            in owner.logger.records if level == "info"))

    def test_force_cannot_override_an_active_physical_limit(self):
        owner = RuntimePlugin()
        gate = FakeDevice(100, "Main Gate", props=base_props())
        runtime = gate_plugin.GateRuntime(owner, gate)
        runtime.start()
        runtime.force("open", pause_seconds=30)
        self.assertEqual("closed", runtime.machine.state)
        self.assertEqual("closed", gate.states["position"])

    def test_control_uses_indigo_server_managed_duration(self):
        calls = []
        fake_indigo.device = types.SimpleNamespace(
            turnOn=lambda device_id, duration: calls.append((device_id, duration)))
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        gate = FakeDevice(100, "Main Gate", props={
            "controlDeviceId": "44", "controlPulseSeconds": "0.75"})
        plugin.pulseGate(None, gate)
        self.assertEqual([(44, 0.75)], calls)
        self.assertFalse(gate.states["onOffState"])

    def test_homekit_door_state_contract_matches_existing_facade(self):
        self.assertEqual({
            "open": 0, "closed": 1, "opening": 2, "closing": 3,
            "stopped": 4, "unknown": 4, "fault": 4, "paused": 4,
        }, gate_plugin.DOOR_STATE)

    def test_compatibility_variable_receives_transition_string(self):
        fake_indigo.variables[7] = FakeVariable(7, "GateMotion", "closed")
        plugin = gate_plugin.Plugin("id", "name", "version", {})
        gate = FakeDevice(100, "Main Gate", props={
            "compatibilityVariableId": "7"})
        plugin.publish_compatibility_state(gate, "opening")
        self.assertEqual("opening", fake_indigo.variables[7].value)


if __name__ == "__main__":
    unittest.main()
