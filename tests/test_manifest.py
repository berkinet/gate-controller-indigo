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
        self.assertEqual("0.1.0-beta.5", info["PluginVersion"])

    def test_all_xml_files_parse(self):
        for name in ("Devices.xml", "Actions.xml", "Events.xml",
                     "PluginConfig.xml"):
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

    def test_logging_menu_has_the_supported_levels(self):
        config = ET.parse(SERVER / "PluginConfig.xml").getroot()
        field = next(node for node in config.findall("Field")
                     if node.attrib.get("id") == "loggingLevel")
        self.assertEqual("20", field.attrib["defaultValue"])
        self.assertEqual(
            [("5", "Detailed debugging"), ("10", "Debugging"),
             ("20", "Informational"),
             ("30", "Warning"), ("40", "Error")],
            [(option.attrib["value"], option.text)
             for option in field.find("List").findall("Option")])

    def test_status_indicator_configuration_is_optional_and_invertible(self):
        device = ET.parse(SERVER / "Devices.xml").getroot().find("Device")
        fields = {field.attrib.get("id"): field
                  for field in device.find("ConfigUI").findall("Field")}
        self.assertEqual("0", fields["indicatorDeviceId"].attrib["defaultValue"])
        self.assertEqual(
            "getIndicatorDeviceList",
            fields["indicatorDeviceId"].find("List").attrib["method"])
        self.assertEqual("false", fields["indicatorInverted"].attrib["defaultValue"])

    def test_second_leaf_delay_and_physical_limits_are_mutually_visible(self):
        device = ET.parse(SERVER / "Devices.xml").getroot().find("Device")
        fields = {field.attrib.get("id"): field
                  for field in device.find("ConfigUI").findall("Field")}
        self.assertEqual("true", fields["delayAfterFirstLeaf"].attrib["defaultValue"])
        self.assertEqual("10", fields["secondLeafOpeningDelaySeconds"].attrib[
            "defaultValue"])
        self.assertEqual("0", fields["secondLeafClosingDelaySeconds"].attrib[
            "defaultValue"])
        for field_id in ("secondLeafOpeningDelaySeconds",
                         "secondLeafClosingDelaySeconds"):
            self.assertEqual("true", fields[field_id].attrib[
                "visibleBindingValue"])
        for field_id in ("open2DeviceId", "open2StateId", "open2ActiveWhen",
                         "closed2DeviceId", "closed2StateId",
                         "closed2ActiveWhen"):
            self.assertEqual("delayAfterFirstLeaf",
                             fields[field_id].attrib["visibleBindingId"])
            self.assertEqual("false",
                             fields[field_id].attrib["visibleBindingValue"])


if __name__ == "__main__":
    unittest.main()
