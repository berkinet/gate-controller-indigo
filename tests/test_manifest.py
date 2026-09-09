import pathlib
import plistlib
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).parents[1]
BUNDLE = ROOT / "Gate Controller.indigoPlugin" / "Contents"
SERVER = BUNDLE / "Server Plugin"


class ManifestTests(unittest.TestCase):
    def test_plist_identity_and_version(self):
        with (BUNDLE / "Info.plist").open("rb") as handle:
            info = plistlib.load(handle)
        self.assertEqual(
            "com.berkinet.indigoplugin.gate-controller",
            info["CFBundleIdentifier"])
        self.assertEqual("0.1.0-alpha.6", info["PluginVersion"])

    def test_all_xml_files_parse(self):
        for name in ("Devices.xml", "Actions.xml", "Events.xml"):
            with self.subTest(name=name):
                ET.parse(SERVER / name)

    def test_declared_callbacks_exist(self):
        source = (SERVER / "plugin.py").read_text(encoding="utf-8")
        callbacks = set()
        for name in ("Devices.xml", "Actions.xml", "Events.xml"):
            root = ET.parse(SERVER / name).getroot()
            callbacks.update(node.text for node in root.iter("CallbackMethod"))
        for callback in callbacks:
            with self.subTest(callback=callback):
                self.assertRegex(source, r"def\s+" + re.escape(callback) + r"\s*\(")

    def test_events_match_runtime_event_ids(self):
        declared = {node.attrib["id"] for node in
                    ET.parse(SERVER / "Events.xml").getroot().findall("Event")}
        expected = {"opening", "closing", "open", "closed", "stopped",
                    "unknown", "paused", "fault", "openTooLong"}
        self.assertEqual(expected, declared)

    def test_gate_position_is_the_textual_display_state(self):
        device = ET.parse(SERVER / "Devices.xml").getroot().find("Device")
        self.assertEqual("position", device.findtext("UiDisplayStateId"))
        position = next(state for state in device.find("States").findall("State")
                        if state.attrib["id"] == "position")
        self.assertEqual("String", position.findtext("ValueType"))


if __name__ == "__main__":
    unittest.main()
