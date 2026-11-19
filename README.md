# PSOPT HMI ECG monitor

ECG acquisition and HF-HRV-based game adaptation using the PLUX Python API,
with an optional separate window for waveform and decision monitoring.

The repository includes the controller, analysis code, native PLUX drivers,
offline regression checks, and Windows packaging tools. Use the Python version
and architecture matching your bundled driver. Configure `webserver` and
`ECG_DEVICES` in `ECG_Device_Controller_v2.py` for your experiment, and use the
same session identifier in the game and controller.

Clone the repository, then run commands from its root:

```bash
git clone https://github.com/ymliu17/PSOPT-HMI.git
cd PSOPT-HMI
```

Run from this directory in the existing PSOPT Python environment:

```bash
python ECG_Device_Controller_v2.py SESSION_ID monitor
```

On Apple Silicon, Python 3.11 uses the bundled `M1_311` driver. Install the
analysis dependencies in your environment and use the interpreter explicitly:

```bash
python3.11 ECG_Device_Controller_v2.py SESSION_ID monitor
```

There is currently no project-specific virtual environment. The controller
selects `M1_311` for Apple Silicon Python 3.11 and resolves the driver directory
relative to the script. Intel Mac and Windows use their corresponding bundled
driver directories. macOS must allow the trusted PLUX binary before it can load.

If device discovery reports `Spawn Status 13`, check that the Bluetooth helper
is executable. For this Mac's Python 3.11 driver, restore the owner execute bit:

```bash
chmod u+x PLUX-API-Python3/M1_311/bth_macprocess
```

The helper is separate from `plux.so`; macOS may also request approval for
`bth_macprocess`. Allowing the library does not necessarily allow the helper.
See the [PLUX macOS setup instructions](https://github.com/pluxbiosignals/python-samples).

After opening a device, the controller sets a five-second receive timeout and
checks the battery before reporting `Connected to ECG device ...; battery: ...%`.
A native `[BTH macOs] Timeout` message alone does not establish failure: the
battery response verifies communication. A failed check closes that connection
and propagates the error. Charge below 10% produces a warning; the existing
acquisition and decision rules are unchanged.

On Windows, double-click `Start_ECG_Monitor_v2.bat` and enter the session ID.
The original command and `Start_ECG_Recording_v2.bat` keep monitoring **off**:

```bash
python ECG_Device_Controller_v2.py SESSION_ID
```

The separate window opens when ECG acquisition starts. It displays:

- **ECG waveforms:** the latest five seconds of raw CH2 during acquisition;
  after recording, the complete block's raw ADC values and cleaned ECG in mV.
  CH2 matches the controller's existing `raw_signal[2]` input.
- **HF-HRV / shapelet decision:** the actual eight overlapping 30-second
  analysis windows, their start/end times, and ln(HF-HRV) values. The view
  switches to this tab when the first window finishes processing.
- Shapelet A/B and the completed HF-HRV trend, standardized only for display;
  the actual Spearman rho values and threshold (currently 0.2); the controller's
  `IncreaseDifficulty` decision; and whether the API accepted the upload.

Waveforms use min/max reduction for display. Analysis and CSV files retain
their full data. The monitor observes existing results; it does not recompute
HF-HRV, change the decision rule, or make API requests. Invalid numeric results
are shown as unavailable while the controller's actual decision remains visible.
The original analysis requires at least 90 seconds of ECG. This change does not
add a decision fallback for short/invalid recordings or change existing analysis
error handling.

The completed block remains visible until the next acquisition begins. Closing
the window keeps the session running; it reopens at the next block. Display
failures do not stop acquisition, computation, CSV saving, or API calls.
The window closes and temporary snapshots are removed when the driver exits.

The viewer uses **Tkinter** in the same Python environment as the controller,
with no additional plotting dependencies or web server. Check it with
`python -m tkinter`. Existing PLUX, NumPy, pandas, SciPy, NeuroKit2, requests,
and Matplotlib requirements still apply to the controller. Continue using the
Python version and PLUX binary that already work with the device.

For an existing Windows environment, keep its working dependency versions.
For a new Windows Python 3.10 x64 environment, use
`requirements-windows-py310.lock.txt` for the locked dependency set.

Offline regression checks (no device or API connection):

```bash
python -m unittest -v test_ecg_monitor.py
```

## Windows distribution

Build a complete Windows source/driver package from this checkout:

```bash
python packaging/build_windows_package.py --version 2026-11-19
```

The archive is written to `dist/`. Its root contains the Windows launchers,
environment checker, optional `Setup_Environment.bat`, locked dependencies,
and the Windows native drivers. The setup script expects Python 3.10 x64 to
already be installed; it creates a local `.venv` and installs dependencies.
See [Windows instructions](packaging/windows/README_WINDOWS.txt).
Builds use an explicit file list and verify the extracted archive with the
regression suite. Windows acquisition must still be checked on the target PC.

## Data and third-party files

Experiment CSVs, recordings, logs, virtual environments, and generated archives
are excluded by `.gitignore` and remain local. No participant data is included.

PLUX native binaries are supplied by the
[PLUX Python samples project](https://github.com/pluxbiosignals/python-samples).
See [upstream license copy](packaging/windows/third_party/PLUX-python-samples-LICENSE.txt)
and [provenance](packaging/windows/third_party/PLUX-SOURCE.txt). That upstream
license file is not a new license grant for this project's application code.
