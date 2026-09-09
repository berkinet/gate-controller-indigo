import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MODULE_PATH = (ROOT / "Gate Controller.indigoPlugin" / "Contents" /
               "Server Plugin" / "gate_state.py")
SPEC = importlib.util.spec_from_file_location("gate_state", MODULE_PATH)
gate_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate_state)


class InputPolarityTests(unittest.TestCase):
    def test_common_boolean_values(self):
        for value in (True, 1, "1.0", "true", "ON", "active", "closed"):
            self.assertTrue(gate_state.input_active(value))
        for value in (False, 0, "0.0", "false", "OFF", "open", "inactive", ""):
            self.assertFalse(gate_state.input_active(value))

    def test_inverted_polarity(self):
        self.assertFalse(gate_state.input_active(True, "false"))
        self.assertTrue(gate_state.input_active(False, "false"))


class GateStateMachineTests(unittest.TestCase):
    def machine(self):
        return gate_state.GateStateMachine(
            debounce=0.10, idle_timeout=2.5, fast=0.8, slow=1.6, band=0.1)

    @staticmethod
    def pulse(machine, timestamp):
        machine.observe(timestamp - 0.01, False, False, False)
        return machine.observe(timestamp, True, False, False)

    def test_startup_lamp_level_is_not_counted_as_an_edge(self):
        machine = self.machine()
        machine.synchronize(0.0, True, False, False)
        machine.observe(0.1, False, False, False)
        self.assertIsNone(machine.observe(0.8, True, False, False))
        machine.observe(0.9, False, False, False)
        transition = machine.observe(1.6, True, False, False)
        self.assertEqual("closing", transition.new)

    def test_physical_limits_dominate_lamp_classification(self):
        machine = self.machine()
        transition = machine.synchronize(0, False, False, True)
        self.assertEqual("closed", transition.new)
        transition = machine.observe(1, True, True, False)
        self.assertEqual("open", transition.new)
        transition = machine.observe(2, False, True, True)
        self.assertEqual("fault", transition.new)

    def test_fast_and_slow_pulses_classify_direction(self):
        fast = self.machine()
        fast.synchronize(0, False, False, False)
        self.pulse(fast, 1.0)
        self.assertEqual("closing", self.pulse(fast, 1.8).new)

        slow = self.machine()
        slow.synchronize(0, False, False, False)
        self.pulse(slow, 1.0)
        self.assertEqual("opening", self.pulse(slow, 2.6).new)

    def test_idle_infers_end_position_from_last_direction(self):
        machine = self.machine()
        machine.synchronize(0, False, False, False)
        self.pulse(machine, 1.0)
        self.pulse(machine, 2.6)
        transition = machine.idle(5.1)
        self.assertEqual("open", transition.new)
        self.assertIn("after opening", transition.reason)

    def test_unclassified_pulses_end_as_stopped(self):
        machine = self.machine()
        machine.synchronize(0, False, False, False)
        self.pulse(machine, 1.0)
        self.pulse(machine, 2.2)
        transition = machine.idle(4.7)
        self.assertEqual("stopped", transition.new)

    def test_debounce_rejects_too_close_edge(self):
        machine = self.machine()
        machine.synchronize(0, False, False, False)
        self.pulse(machine, 1.0)
        self.assertIsNone(self.pulse(machine, 1.05))
        self.assertEqual(1.0, machine.last_edge)

    def test_force_pause_ignores_pulses_but_not_limits(self):
        machine = self.machine()
        machine.synchronize(0, False, False, False)
        transition = machine.force("paused", 1.0, pause_seconds=10)
        self.assertEqual("paused", transition.new)
        self.assertIsNone(self.pulse(machine, 2.0))
        transition = machine.observe(3.0, False, False, True)
        self.assertEqual("closed", transition.new)


if __name__ == "__main__":
    unittest.main()
