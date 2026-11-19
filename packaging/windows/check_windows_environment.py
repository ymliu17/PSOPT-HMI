"""Check Python, dependencies and native-driver loading without device/API calls."""

import importlib
from pathlib import Path
import platform
import struct
import sys


def main():
    print("Python: {} ({}, {}-bit)".format(sys.executable, platform.python_version(), struct.calcsize("P") * 8))
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        print("This distribution requires Windows with a 64-bit Python interpreter.")
        return 1
    root = Path(__file__).resolve().parent
    version = "{}{}".format(sys.version_info.major, sys.version_info.minor)
    driver = root / "PLUX-API-Python3" / ("Win64_" + version)
    if not (driver / "plux.pyd").is_file():
        print("No bundled driver matches this Python: {}".format(driver))
        print("Use your working Python 3.7/3.8/3.9/3.10 x64 ECG environment.")
        return 1
    failed = False
    for module in ("numpy", "pandas", "scipy", "neurokit2", "requests", "matplotlib", "sklearn", "tkinter"):
        try:
            importlib.import_module(module)
            print("OK: " + module)
        except Exception as exc:
            print("FAIL: {}: {}".format(module, exc))
            failed = True
    if failed:
        print("Activate your original environment, or see Setup_Environment.bat for a fresh Python 3.10 environment.")
        return 1
    try:
        sys.path.insert(0, str(driver))
        plux = importlib.import_module("plux")
        print("OK: PLUX {} ({})".format(getattr(plux, "version", "unknown version"), plux.__file__))
    except Exception as exc:
        print("FAIL: PLUX: {}".format(exc))
        print("For DLL load errors, check the x64 Microsoft Visual C++ runtime; see README_WINDOWS.txt.")
        return 1
    print("Environment check passed. No Bluetooth connection or API request was made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
