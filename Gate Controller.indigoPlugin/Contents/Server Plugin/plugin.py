# -*- coding: utf-8 -*-

"""Indigo Gate Controller plugin."""

import datetime
import threading
import time

import indigo

from gate_state import GateStateMachine, input_active


DOOR_STATE = {
    "open": 0, "closed": 1, "opening": 2, "closing": 3,
    "stopped": 4, "unknown": 4, "fault": 4, "paused": 4,
}


class GateRuntime:
    REQUIRED_INPUTS = ("lamp", "open", "closed")
    OPTIONAL_INPUTS = ("open2", "closed2", "safety1", "safety2",
                       "cycle", "lock1", "lock2")
    INPUTS = REQUIRED_INPUTS + OPTIONAL_INPUTS

    def __init__(self, plugin, device):
        self.plugin = plugin
        self.device = device
        p = device.pluginProps
        self.machine = GateStateMachine(
            debounce=float(p.get("debounceSeconds", 0.10)),
            idle_timeout=float(p.get("idleTimeoutSeconds", 2.5)),
            fast=float(p.get("closingInterval", 0.80)),
            slow=float(p.get("openingInterval", 1.60)),
            band=float(p.get("intervalBand", 0.10)))
        self._lock = threading.RLock()
        self._generation = 0
        self._idle_timer = None
        self._open_timer = None
        self._stopped = False
        self._input_error_message = None
        self._input_error_logged_at = 0.0

    def source_ids(self):
        result = set()
        for prefix in self.INPUTS:
            try:
                result.add(int(self.device.pluginProps.get(prefix + "DeviceId", 0)))
            except (TypeError, ValueError):
                pass
        result.discard(0)
        return result

    def _input(self, prefix, required=True):
        props = self.device.pluginProps
        source_id = int(props.get(prefix + "DeviceId", 0) or 0)
        state_id = str(props.get(prefix + "StateId", "") or "")
        if not source_id or not state_id:
            if required:
                raise RuntimeError("%s input is not configured" % prefix)
            return None
        try:
            source = indigo.devices[source_id]
        except Exception:
            raise RuntimeError("%s input device id %s is unavailable" %
                               (prefix, source_id))
        if not getattr(source, "enabled", True):
            raise RuntimeError("%s input device '%s' is disabled" %
                               (prefix, source.name))
        if state_id not in source.states:
            raise RuntimeError("%s input state '%s' is unavailable on '%s'" %
                               (prefix, state_id, source.name))
        return input_active(
            source.states[state_id], props.get(prefix + "ActiveWhen", "true"))

    def _read_inputs(self):
        values = {prefix: self._input(prefix, prefix in self.REQUIRED_INPUTS)
                  for prefix in self.INPUTS}

        open_active = values["open"]
        closed_active = values["closed"]
        if values["open2"] is not None:
            open_active = open_active and values["open2"]
        if values["closed2"] is not None:
            closed_active = closed_active and values["closed2"]

        primary_conflict = values["open"] and values["closed"]
        secondary_conflict = (values["open2"] is not None and
                              values["closed2"] is not None and
                              values["open2"] and values["closed2"])
        if primary_conflict or secondary_conflict:
            open_active = closed_active = True
        return values, open_active, closed_active

    def _publish_inputs(self, values):
        keys = {
            "lamp": "lampInputActive",
            "open": "openLimitActive",
            "closed": "closedLimitActive",
            "open2": "open2LimitActive",
            "closed2": "closed2LimitActive",
            "safety1": "safety1Active",
            "safety2": "safety2Active",
            "cycle": "cycleActive",
            "lock1": "lock1Active",
            "lock2": "lock2Active",
        }
        updates = []
        for prefix, value in values.items():
            state_id = keys[prefix]
            normalized = bool(value)
            if self.device.states.get(state_id) != normalized:
                updates.append({"key": state_id, "value": normalized})
        if updates:
            self.device.updateStatesOnServer(updates)

    def start(self):
        with self._lock:
            try:
                values, open_active, closed_active = self._read_inputs()
                transition = self.machine.synchronize(
                    time.monotonic(), values["lamp"], open_active, closed_active)
                self._publish_inputs(values)
                self._inputs_recovered()
                self.device.updateStateOnServer("onOffState", value=False)
            except Exception as error:
                self._input_error(error)
                return
        self._publish(transition, notify=False)

    def stop(self):
        with self._lock:
            self._stopped = True
            self._generation += 1
            timers = (self._idle_timer, self._open_timer)
            self._idle_timer = self._open_timer = None
        for timer in timers:
            if timer is not None:
                timer.cancel()

    def _replace_timer(self, attribute, delay, callback):
        old = getattr(self, attribute)
        if old is not None:
            old.cancel()
        generation = self._generation
        timer = threading.Timer(max(0.0, delay), callback, (generation,))
        timer.daemon = True
        setattr(self, attribute, timer)
        timer.start()

    def _schedule_idle(self, now):
        if self.machine.idle_deadline is None:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
                self._idle_timer = None
            return
        self._replace_timer(
            "_idle_timer", self.machine.idle_deadline - now, self._idle_fired)

    def _idle_fired(self, generation):
        with self._lock:
            if self._stopped or generation != self._generation:
                return
            self._idle_timer = None
            try:
                values, open_active, closed_active = self._read_inputs()
                self._publish_inputs(values)
                self._inputs_recovered()
                transition = self.machine.idle(
                    time.monotonic(), open_active, closed_active)
            except Exception as error:
                self._input_error(error)
                return
        self._publish(transition)

    def _open_too_long_fired(self, generation):
        with self._lock:
            if (self._stopped or generation != self._generation or
                    self.machine.state not in ("opening", "open")):
                return
            self._open_timer = None
        try:
            self.device.updateStateOnServer("openTooLong", value=True)
            self.plugin.emit(self.device, "openTooLong")
            self.plugin.run_action_group(self.device, "openTooLongActionGroup")
        except Exception as error:
            self.plugin.logger.error(
                "Unable to publish open-too-long state for '%s': %s",
                self.device.name, error)

    def _manage_open_timer(self, transition):
        if transition is None:
            return
        if transition.new == "opening":
            seconds = float(self.device.pluginProps.get("openTooLongSeconds", 1800))
            self.device.updateStateOnServer("openTooLong", value=False)
            if seconds > 0:
                self._replace_timer("_open_timer", seconds, self._open_too_long_fired)
        elif transition.new != "open":
            if self._open_timer is not None:
                self._open_timer.cancel()
                self._open_timer = None
            self.device.updateStateOnServer("openTooLong", value=False)

    def _input_error(self, error):
        message = str(error)
        self.device.setErrorStateOnServer(message)
        self.device.updateStatesOnServer([
            {"key": "inputsAvailable", "value": False},
            {"key": "status", "value": "inputs unavailable: " + message},
        ])
        now = time.monotonic()
        try:
            reminder = float(self.device.pluginProps.get(
                "inputErrorReminderSeconds", 3600) or 3600)
        except (TypeError, ValueError):
            reminder = 3600.0
        if (message != self._input_error_message or
                now - self._input_error_logged_at >= reminder):
            self.plugin.logger.warning(
                "Gate inputs unavailable; retaining last known position: "
                "device='%s': %s", self.device.name, message)
            self._input_error_logged_at = now
        self._input_error_message = message

    def _inputs_recovered(self):
        recovered = self._input_error_message is not None
        if recovered:
            self.plugin.logger.info(
                "Gate inputs recovered: device='%s'", self.device.name)
        self._input_error_message = None
        self._input_error_logged_at = 0.0
        if recovered or self.device.states.get("inputsAvailable") is not True:
            self.device.setErrorStateOnServer(None)
            self.device.updateStateOnServer("inputsAvailable", value=True)
        if recovered:
            self.device.updateStateOnServer(
                "status", value="inputs recovered; position retained")

    def evaluate(self, reason="input changed"):
        with self._lock:
            if self._stopped:
                return
            try:
                values, open_active, closed_active = self._read_inputs()
                now = time.monotonic()
                transition = self.machine.observe(
                    now, values["lamp"], open_active, closed_active)
                self._publish_inputs(values)
                self._inputs_recovered()
                self._schedule_idle(now)
            except Exception as error:
                self._input_error(error)
                return
        self._publish(transition)

    def _publish(self, transition, notify=True):
        try:
            if transition is None:
                if self.machine.last_interval is not None:
                    self.device.updateStateOnServer(
                        "lampInterval", value=round(self.machine.last_interval, 3))
                return
            state = transition.new
            updates = [
                {"key": "position", "value": state,
                 "uiValue": state.capitalize()},
                {"key": "doorState", "value": DOOR_STATE[state]},
                {"key": "motionActive", "value": state in ("opening", "closing")},
                {"key": "fault", "value": state == "fault"},
                {"key": "status", "value": transition.reason},
                {"key": "lastTransition", "value": datetime.datetime.now().isoformat(" ", "seconds")},
            ]
            if self.machine.last_interval is not None:
                updates.append({"key": "lampInterval",
                                "value": round(self.machine.last_interval, 3)})
            self.device.updateStatesOnServer(updates)
            self._manage_open_timer(transition)
            if transition.old == transition.new:
                self.plugin.logger.info(
                    "Gate state synchronized: device='%s' %s (%s)",
                    self.device.name, transition.new, transition.reason)
            else:
                self.plugin.logger.info(
                    "Gate state changed: device='%s' %s -> %s (%s)",
                    self.device.name, transition.old, transition.new,
                    transition.reason)
            if notify:
                self.plugin.emit(self.device, state)
                self.plugin.run_action_group(self.device, state + "ActionGroup")
        except Exception as error:
            self.plugin.logger.error(
                "Unable to publish gate state for '%s': %s",
                self.device.name, error)

    def force(self, state, pause_seconds=0.0):
        with self._lock:
            now = time.monotonic()
            transition = self.machine.force(state, now, pause_seconds)
            try:
                values, open_active, closed_active = self._read_inputs()
                self._publish_inputs(values)
                self._inputs_recovered()
                limit_transition = self.machine.observe(
                    now, values["lamp"], open_active, closed_active)
                if limit_transition is not None:
                    transition = limit_transition
            except Exception as error:
                self._input_error(error)
                return
            self._schedule_idle(now)
        self._publish(transition)


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.runtimes = {}
        self.source_index = {}
        self.triggers = {}
        self._lock = threading.RLock()

    def startup(self):
        indigo.devices.subscribeToChanges()
        self.logger.info("Gate Controller alpha started")

    def shutdown(self):
        for runtime in list(self.runtimes.values()):
            runtime.stop()
        self.runtimes.clear()
        self.source_index.clear()

    def deviceStartComm(self, device):
        self.deviceStopComm(device)
        try:
            runtime = GateRuntime(self, device)
            self.runtimes[device.id] = runtime
            for source_id in runtime.source_ids():
                self.source_index.setdefault(source_id, set()).add(device.id)
            runtime.start()
        except Exception as error:
            device.setErrorStateOnServer(str(error))
            self.logger.error("Unable to start gate '%s': %s", device.name, error)

    def deviceStopComm(self, device):
        runtime = self.runtimes.pop(device.id, None)
        if runtime is None:
            return
        runtime.stop()
        for source_id in list(self.source_index):
            self.source_index[source_id].discard(device.id)
            if not self.source_index[source_id]:
                del self.source_index[source_id]

    def deviceUpdated(self, original, updated):
        for gate_id in list(self.source_index.get(updated.id, ())):
            runtime = self.runtimes.get(gate_id)
            if runtime is not None:
                runtime.evaluate("input changed")

    def triggerStartProcessing(self, trigger):
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.triggers.pop(trigger.id, None)

    def emit(self, device, event_id):
        for trigger in list(self.triggers.values()):
            try:
                if (trigger.pluginTypeId == event_id and
                        int(trigger.pluginProps.get("gateDeviceId", 0)) == device.id):
                    indigo.trigger.execute(trigger.id)
            except Exception as error:
                self.logger.error("Unable to execute gate trigger %s for '%s': %s",
                                  trigger.id, device.name, error)

    def run_action_group(self, device, property_name):
        try:
            group_id = int(device.pluginProps.get(property_name, 0) or 0)
            if group_id:
                indigo.actionGroup.execute(group_id)
        except Exception as error:
            self.logger.error("Unable to run %s for gate '%s': %s",
                              property_name, device.name, error)

    def pulseGate(self, action, device):
        try:
            control_id = int(device.pluginProps.get("controlDeviceId", 0) or 0)
            if not control_id:
                raise RuntimeError("no gate control device is configured")
            seconds = float(device.pluginProps.get("controlPulseSeconds", 1.0))
            indigo.device.turnOn(control_id, duration=seconds)
            device.updateStateOnServer("onOffState", value=False)
        except Exception as error:
            self.logger.error("Unable to start gate control pulse for '%s': %s",
                              device.name, error)

    def forceGateState(self, action, device):
        try:
            self.runtimes[device.id].force(
                str(action.props.get("state", "unknown")),
                float(action.props.get("pauseSeconds", 0)))
        except Exception as error:
            self.logger.error("Unable to force state for gate '%s': %s",
                              device.name, error)

    def clearGateFault(self, action, device):
        try:
            runtime = self.runtimes[device.id]
            if runtime.machine.state == "fault":
                runtime.force("unknown")
            runtime.evaluate("clear fault")
        except Exception as error:
            self.logger.error("Unable to clear fault for gate '%s': %s",
                              device.name, error)

    def actionControlDevice(self, action, device):
        if action.deviceAction in (indigo.kDeviceAction.TurnOn,
                                   indigo.kDeviceAction.TurnOff,
                                   indigo.kDeviceAction.Toggle):
            self.pulseGate(action, device)

    def getGateDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        return [(d.id, d.name) for d in indigo.devices.iter("self.gateController")]

    def getSourceDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        result = [(0, "— None —")] if str(filter) == "optional" else []
        result.extend((d.id, d.name) for d in indigo.devices
                      if getattr(d, "enabled", True) and d.id != targetId)
        return result

    def getActionGroupList(self, filter="", valuesDict=None, typeId="", targetId=0):
        result = [(0, "— None —")]
        result.extend((group.id, group.name) for group in indigo.actionGroups)
        return result

    def getStateList(self, filter="", valuesDict=None, typeId="", targetId=0):
        valuesDict = valuesDict or {}
        try:
            device_id = int(valuesDict.get(str(filter) + "DeviceId", 0))
            device = indigo.devices[device_id]
            return [(state_id, state_id) for state_id in sorted(device.states)]
        except Exception:
            return []

    def sourceDeviceChanged(self, valuesDict, typeId, deviceId):
        for prefix in GateRuntime.INPUTS:
            try:
                source_id = int(valuesDict.get(prefix + "DeviceId", 0) or 0)
                state_id = str(valuesDict.get(prefix + "StateId", "") or "")
                if not source_id or state_id not in indigo.devices[source_id].states:
                    valuesDict[prefix + "StateId"] = ""
            except Exception:
                valuesDict[prefix + "StateId"] = ""
        return valuesDict

    def validateDeviceConfigUi(self, valuesDict, typeId, deviceId):
        errors = indigo.Dict()
        for prefix, label in (("lamp", "Flashing lamp"),
                              ("open", "Open detector"),
                              ("closed", "Closed detector")):
            try:
                source = indigo.devices[int(valuesDict.get(prefix + "DeviceId", 0))]
                state_id = str(valuesDict.get(prefix + "StateId", ""))
                if not state_id or state_id not in source.states:
                    errors[prefix + "StateId"] = "%s state is required" % label
            except Exception:
                errors[prefix + "DeviceId"] = "%s device is required" % label
        for prefix, label in (("open2", "Second open detector"),
                              ("closed2", "Second closed detector"),
                              ("safety1", "Safety input 1"),
                              ("safety2", "Safety input 2"),
                              ("cycle", "Active-cycle input"),
                              ("lock1", "Lock input 1"),
                              ("lock2", "Lock input 2")):
            try:
                source_id = int(valuesDict.get(prefix + "DeviceId", 0) or 0)
            except (TypeError, ValueError):
                source_id = 0
                errors[prefix + "DeviceId"] = "%s device is invalid" % label
            state_id = str(valuesDict.get(prefix + "StateId", "") or "")
            if source_id:
                try:
                    source = indigo.devices[source_id]
                    if not state_id or state_id not in source.states:
                        errors[prefix + "StateId"] = "%s state is required" % label
                except Exception:
                    errors[prefix + "DeviceId"] = "%s device is unavailable" % label
        pairs = [(valuesDict.get(p + "DeviceId"), valuesDict.get(p + "StateId"))
                 for p in ("open", "closed")]
        if pairs[0] == pairs[1]:
            errors["closedDeviceId"] = "Open and closed detectors must be different"
        for key, minimum in (("debounceSeconds", 0.01),
                             ("idleTimeoutSeconds", 0.2),
                             ("controlPulseSeconds", 0.1),
                             ("closingInterval", 0.1),
                             ("openingInterval", 0.1),
                             ("intervalBand", 0.01),
                             ("inputErrorReminderSeconds", 10.0)):
            try:
                if float(valuesDict.get(key, 0)) < minimum:
                    raise ValueError()
            except (TypeError, ValueError):
                errors[key] = "Enter a number of at least %s" % minimum
        try:
            closing = float(valuesDict.get("closingInterval", 0))
            opening = float(valuesDict.get("openingInterval", 0))
            band = float(valuesDict.get("intervalBand", 0))
            idle = float(valuesDict.get("idleTimeoutSeconds", 0))
            debounce = float(valuesDict.get("debounceSeconds", 0))
            if abs(opening - closing) <= 2 * band:
                errors["intervalBand"] = "Opening and closing ranges must not overlap"
            if idle <= max(opening, closing) + band:
                errors["idleTimeoutSeconds"] = "Idle timeout must exceed both pulse ranges"
            if debounce >= min(opening, closing) - band:
                errors["debounceSeconds"] = "Debounce must be below both pulse ranges"
        except (TypeError, ValueError):
            pass
        try:
            if float(valuesDict.get("openTooLongSeconds", 0)) < 0:
                raise ValueError()
        except (TypeError, ValueError):
            errors["openTooLongSeconds"] = "Enter zero to disable, or a positive number"
        return (False, valuesDict, errors) if errors else (True, valuesDict)
