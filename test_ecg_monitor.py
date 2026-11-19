"""Offline checks; no device, display, or network connection is required."""

import argparse
import ast
from contextlib import nullcontext, redirect_stdout
import io
import json
import math
import platform
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import ecg_monitor as monitor


ROOT = Path(__file__).resolve().parent


class DriverCompatibilityTests(unittest.TestCase):
    def connection_namespace(self, device):
        tree = ast.parse((ROOT / "ECG_Device_Controller_v2.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "connectToDevice")
        ns = {"plux": SimpleNamespace(SignalsDev=SimpleNamespace(findDevices=lambda: (("TEST", "ECG"),))),
              "NewDevice": Mock(return_value=device), "ECG_DEVICES": ["TEST"],
              "frequency": 1000, "time": SimpleNamespace(sleep=lambda _: None)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "connection", "exec"), ns)
        return ns

    def test_connection_requires_battery_response_and_reports_low_charge(self):
        device = Mock()
        device.getBattery.return_value = 1.55
        ns = self.connection_namespace(device)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertIs(ns["connectToDevice"](), device)
        device.setTimeout.assert_called_once_with(5000)
        device.getBattery.assert_called_once()
        device.close.assert_not_called()
        self.assertIn("battery: 1.55%", output.getvalue())
        self.assertIn("Low ECG battery", output.getvalue())
        self.assertEqual(device.frequency, 1000)

    def test_failed_health_check_closes_device_without_reporting_connected(self):
        device = Mock()
        device.getBattery.side_effect = RuntimeError("Device did not respond")
        ns = self.connection_namespace(device)
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, "Device did not respond"):
            ns["connectToDevice"]()
        device.close.assert_called_once()
        self.assertNotIn("Connected to ECG device", output.getvalue())

    def test_driver_matches_interpreter_and_resolves_from_script(self):
        tree = ast.parse((ROOT / "ECG_Device_Controller_v2.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "_plux_directory")
        ns = {"sys": sys, "platform": platform, "__file__": str(ROOT / "ECG_Device_Controller_v2.py")}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "loader", "exec"), ns)
        for system, machine, bits, expected in (
            ("Darwin", "arm64", 64, "M1_311"),
            ("Darwin", "x86_64", 64, "MacOS/Intel311"),
            ("Windows", "AMD64", 64, "Win64_311"),
            ("Windows", "x86", 32, "Win32_311"),
            ("Linux", "x86_64", 64, "Linux64"),
        ):
            with self.subTest(system=system, machine=machine), \
                    patch.object(platform, "system", return_value=system), \
                    patch.object(platform, "machine", return_value=machine), \
                    patch.object(sys, "version_info", SimpleNamespace(major=3, minor=11)), \
                    patch.object(sys, "maxsize", 2**(bits - 1) - 1):
                self.assertEqual(ns["_plux_directory"](), ROOT / "PLUX-API-Python3" / expected)

    def test_device_supports_native_new_with_object_init(self):
        tree = ast.parse((ROOT / "ECG_Device_Controller_v2.py").read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "NewDevice")

        class SignalsDev:
            # Match the installed PLUX binding: __new__ consumes the address,
            # while __init__ is inherited directly from object.
            def __new__(cls, address):
                instance = super().__new__(cls)
                instance.address = address
                return instance

        ns = {"plux": SimpleNamespace(SignalsDev=SignalsDev), "dataList": []}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), "device", "exec"), ns)
        device = ns["NewDevice"]("TEST-DEVICE")
        self.assertIs(SignalsDev.__init__, object.__init__)
        self.assertEqual(device.address, "TEST-DEVICE")
        self.assertEqual(device.duration, 0)
        self.assertEqual(device.frequency, 0)
        self.assertFalse(device.stopAcquisition)
        self.assertFalse(device.onRawFrame(1, [100, 200]))
        self.assertEqual(ns["dataList"], [[1, 100, 200]])


def begin(observer, block="block-1"):
    observer.update("begin", block=block, number=1, frequency=1000, threshold=0.2,
                    shapelet_a=list(range(8)), shapelet_b=list(reversed(range(8))))


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.observer = monitor._SnapshotMonitor(self.path, "TEST")
        begin(self.observer)

    def test_disabled_does_not_inspect_signal(self):
        with patch.object(monitor, "_active_monitor", None):
            monitor.publish("samples", rows=object())
            monitor.publish("cleaned", signal=object())

    def test_failure_does_not_escape(self):
        broken = Mock()
        broken.update.side_effect = OSError("disk full")
        with patch.object(monitor, "_active_monitor", broken), redirect_stdout(io.StringIO()):
            monitor.publish("begin")

    def test_correct_channel_rolling_window_and_peak_preservation(self):
        rows = [[i, -123, 32768] for i in range(9000)]
        rows[5001][2] = 60000
        self.observer.update("samples", rows=rows)
        state = json.loads(self.path.read_text())
        self.assertEqual(state["samples"], 9000)
        self.assertEqual(state["duration"], 9)
        self.assertGreaterEqual(state["raw"][0][0], 4)
        self.assertLessEqual(len(state["raw"]), 1200)
        self.assertIn([5.001, 60000], state["raw"])
        self.assertNotIn(-123, [p[1] for p in state["raw"]])

    def test_exact_window_values_invalid_data_and_block_reset(self):
        self.observer.update("window", index=0, start=0, end=30, hf=1.23456)
        self.observer.update("window", index=1, start=8.571, end=38.571, hf=float("nan"))
        self.observer.update("result", rho_a=float("nan"), rho_b=0.2, increase=True)
        self.observer.update("upload", success=False, status_code=503)
        state = json.loads(self.path.read_text())
        self.assertEqual(state["windows"][0]["hf"], 1.23456)
        self.assertIsNone(state["windows"][1]["hf"])
        self.assertIsNone(state["rho_a"])
        self.assertIn("Increase difficulty", monitor.result_text(state))
        self.assertIn("503", state["status"])
        begin(self.observer, "block-2")
        self.assertEqual(self.observer.state["windows"], [])
        self.assertNotIn("increase", self.observer.state)

    def test_short_signal_is_not_shown_as_negative_decision(self):
        self.observer.update("unavailable", message="Too short")
        self.assertEqual(monitor.result_text(self.observer.state), "Decision: unavailable")

    def test_reopen_next_block_and_cleanup_on_error(self):
        first, second = Mock(), Mock()
        first.poll.return_value = None
        second.poll.return_value = None
        with patch.object(monitor.subprocess, "Popen", side_effect=[first, second]) as spawn:
            with self.assertRaisesRegex(RuntimeError, "analysis failed"):
                with monitor.enabled_monitor("TEST"):
                    observer = monitor._active_monitor
                    path = observer.state_path
                    begin(observer)
                    first.poll.return_value = 0
                    observer.update("samples", rows=object())  # Closed viewer skips work.
                    begin(observer, "block-2")
                    self.assertEqual(spawn.call_count, 2)
                    raise RuntimeError("analysis failed")
        second.terminate.assert_called_once()
        self.assertFalse(path.exists())
        self.assertIsNone(monitor._active_monitor)

    def test_startup_failures_are_nonfatal(self):
        with patch.object(monitor.tempfile, "TemporaryDirectory", side_effect=OSError("no temp")):
            with redirect_stdout(io.StringIO()), monitor.enabled_monitor("TEST"):
                monitor.publish("samples", rows=object())
        with patch.object(monitor.subprocess, "Popen", side_effect=OSError("no GUI")):
            with redirect_stdout(io.StringIO()), monitor.enabled_monitor("TEST"):
                monitor.publish("begin", block="B", number=1, frequency=1000, threshold=.2,
                                shapelet_a=[], shapelet_b=[])
                monitor.publish("result", rho_a=.1, rho_b=.5, increase=True)
                self.assertTrue(monitor._active_monitor.state["increase"])


class ControllerTests(unittest.TestCase):
    def namespace(self):
        # Load just the workflow functions: no native PLUX import or live API.
        tree = ast.parse((ROOT / "ECG_Device_Controller_v2.py").read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ("main", "_run_session", "loopDeviceThread")]
        namespace = {"argparse": argparse, "sys": sys, "nullcontext": nullcontext,
                     "enabled_monitor": monitor.enabled_monitor, "_publish_ecg_monitor": monitor.publish}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT / "ECG_Device_Controller_v2.py"), "exec"), namespace)
        return namespace

    def test_main_opt_in_and_argument_validation(self):
        ns = self.namespace()
        run = ns["_run_session"] = Mock()
        ns["enabled_monitor"] = Mock(side_effect=lambda session: nullcontext())
        with patch.object(sys, "argv", ["controller", "TEST"]):
            ns["main"]()
        ns["enabled_monitor"].assert_not_called()
        with patch.object(sys, "argv", ["controller", "TEST", "monitor"]):
            ns["main"]()
        ns["enabled_monitor"].assert_called_once_with("TEST")
        self.assertEqual(run.call_count, 2)
        with patch.object(sys, "argv", ["controller", "TEST", "typo"]), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                ns["main"]()
        self.assertEqual(run.call_count, 2)

    def run_workflow(self, observer):
        ns = self.namespace()
        calls, saved = [], []
        counts = {"block": 0, "status": 0}

        def get(url):
            if "GetByExternalIdentifier" in url:
                data = {"identifier": "SESSION"}
            elif "GetLatestForSession" in url:
                counts["block"] += 1
                data = {"identifier": f"BLOCK-{counts['block']}"}
            else:
                data = {"isGameReady": counts["status"] % 3 != 1}
                counts["status"] += 1
            calls.append(("GET", url))
            return SimpleNamespace(status_code=200, json=lambda: data)

        def put(url, json):
            calls.append(("PUT", url, dict(json)))
            return SimpleNamespace(status_code=200)

        class Frame:
            def __init__(self, rows):
                self.rows = list(rows)

            def __getitem__(self, index):
                return [row[index] for row in self.rows]

        class Thread:
            def __init__(self, target, args):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        def compute(raw, session, block):
            monitor.publish("cleaned", signal=raw)
            for i in range(8):
                monitor.publish("window", index=i, start=i * 10, end=i * 10 + 30, hf=i / 10)
            return list(range(8))

        def compare(values):
            # Exercise both sides of the threshold and its inclusive boundary.
            a = .2 if counts["block"] % 2 else -.5
            return SimpleNamespace(rho=[a]), SimpleNamespace(rho=[-.1])

        device = Mock(frequency=1000)
        device.getBattery.return_value = 80
        device.loop.side_effect = lambda: ns["dataList"].extend([[i, -123, 32768 + i] for i in range(20)])
        bio = SimpleNamespace(shapeletA=list(range(8)), shapeletB=list(range(8)),
                              getHF_HRV=compute, compareShapelets=compare,
                              saveECG=lambda raw, session, block: saved.append((list(raw), session, block)),
                              saveRho=lambda *args: None)
        ns.update(requests=SimpleNamespace(get=get, put=put), bio=bio, pd=SimpleNamespace(DataFrame=Frame),
                  np=SimpleNamespace(asarray=lambda values: values), time=SimpleNamespace(sleep=lambda _: None),
                  threading=SimpleNamespace(Thread=Thread), gc=SimpleNamespace(collect=lambda: None),
                  connectToDevice=lambda: device, webserver="https://offline.invalid", frequency=1000,
                  code=3, r_threshold=.2, requestTime=.5)
        with patch.object(monitor, "_active_monitor", observer), redirect_stdout(io.StringIO()):
            ns["_run_session"]("TEST")
        self.assertEqual(len(saved), 25)
        device.start.assert_called_with(1000, 3, 16)
        return calls, saved

    def test_monitor_preserves_api_requests_raw_samples_and_decisions(self):
        baseline = self.run_workflow(None)
        with tempfile.TemporaryDirectory() as directory:
            observer = monitor._SnapshotMonitor(Path(directory) / "state.json", "TEST")
            self.assertEqual(self.run_workflow(observer), baseline)
            self.assertEqual(observer.state["block"], "BLOCK-25")
            self.assertEqual(len(observer.state["windows"]), 8)
        broken = Mock()
        broken.update.side_effect = OSError("display failed")
        self.assertEqual(self.run_workflow(broken), baseline)
        results = [c[2]["IncreaseDifficulty"] for c in baseline[0] if c[0] == "PUT" and "SaveResult" in c[1]]
        self.assertEqual(results, [i % 2 == 1 for i in range(1, 26)])


if __name__ == "__main__":
    unittest.main()
