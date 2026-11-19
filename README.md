# PSOPT-HMI

ECG-based adaptive game controller for **pSOPT (Personalized Engine for Speed of
Information Processing)**, associated with the **CogT pSOPT Intervention Study**
([NCT06005038](https://clinicaltrials.gov/study/NCT06005038)) at Stanford University.
The study examines cognitive training personalized using physiological feedback
and task performance. This repository provides the ECG acquisition and
physiological decision component: it connects the Brain Wellness Games web app to
a PLUX sensor and uses **high-frequency heart rate variability (HF-HRV)** to
request a difficulty increase after each block.

An optional **ECG monitor** shows the acquired waveform, the analysis windows,
and the actual shapelet correlations and decision sent to the game API.

## Video demo

HRV-HMI workflow overview (4× speed, approximately 16 seconds). This illustrative
video includes RMSSD plots; the current controller implements the HF-HRV pipeline
described below.

https://github.com/user-attachments/assets/4bee90d5-419a-4acb-89e3-9a041e7dfdc7

---

## Table of contents

- [Study](#study)
- [Protocol session workflow](#protocol-session-workflow)
- [Protocol and implementation differences](#protocol-and-implementation-differences)
- [How it works](#how-it-works)
- [Adaptive decision logic](#adaptive-decision-logic)
- [ECG and HF-HRV analysis](#ecg-and-hf-hrv-analysis)
- [Repository layout](#repository-layout)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running a session](#running-a-session)
- [Recorded output](#recorded-output)
- [ECG monitor](#ecg-monitor)
- [Troubleshooting](#troubleshooting)
- [Windows distribution](#windows-distribution)
- [Validation and current limitations](#validation-and-current-limitations)
- [Third-party files](#third-party-files)

---

## Study

| | |
|---|---|
| Registration | [NCT06005038](https://clinicaltrials.gov/study/NCT06005038) |
| Registered title | CogT pSOPT Intervention Study |
| Official title | Personalized Engine for Speed of Information Processing |
| Sponsor / PI | Stanford University / Feng Lin |
| Development stage | R33 pilot trial following R21 intervention development |
| Design | Randomized, parallel groups; participants and outcome assessors masked |
| Registered population | Adults aged 60+; mild or subjective cognitive impairment |
| Enrollment | 50 participants (actual) |
| Status | Completed; study completion 2026-07-31 |
| Registered assessment time points | Baseline, Week 7, and 3-month follow-up |

Registry details reflect the **2026-11-18** update, verified **2026-11-19** against
the [ClinicalTrials.gov record](https://clinicaltrials.gov/study/NCT06005038).

The two study arms are:

- **pSOPT (experimental):** speed-of-processing training personalized with
  physiological feedback and cognitive performance.
- **MLA (comparator):** computerized mental leisure activities, including
  crosswords, Sudoku, and solitaire. ECG is collected in both arms.

This Python entry point supports the pSOPT combined-game workflow. The procedure
manual describes MLA ECG collection separately through **OpenSignals**, without
this Python controller (manual pp. 42–43); there is no study-arm command-line flag.

## Protocol session workflow

The supplied *pSOPT RCT Procedure Manual* describes **6 weeks**, **3 sessions per
week**, and **18 sessions** in total. Each appointment lasts approximately
60 minutes, including roughly 40–45 minutes of active tasks (manual p. 31).

| Stage | Procedure described in the manual |
|---|---|
| Preparation | Set up the participant's game display and operator's computer, pair the ECG device, and check signal quality before the task |
| Orientation | Teach and practice all four games at the first session; refresh instructions when needed |
| Before / after training | Collect fatigue and SAM ratings; the assessment summary also lists 5-minute resting ECG recordings before and after training |
| pSOPT task | 20 blocks of approximately 2 minutes each; between blocks, collect ratings of focus, difficulty, and novelty before continuing |
| MLA task | Approximately 40 minutes with ECG recorded in OpenSignals; the pSOPT between-block questions are not administered |
| Weekly measures | Medical changes/adverse events, mental leisure activity, and physical activity questionnaires |
| After the session | Verify saved data and transfer it to the study's designated storage |

Sources: manual pp. 12–13, 31–32, and 35–43. These are staff-administered study
procedures; the controller does not collect questionnaires, schedule visits,
perform randomization, or automatically record the pre/post resting ECG periods.

The combined task contains four games (manual pp. 37–40):

| Game | Participant task |
|---|---|
| Target Tracker | Track initially marked objects among moving distractors |
| Sound Sweeps | Identify the pitch direction of successive sounds |
| Mixed Signals | Respond when the auditory and visual information match the current rule |
| Task 4 (shape/color/category matching) | Match figures according to the preceding rule cue |

Game presentation and sequencing are handled by the web application. This
controller reads block status and returns the physiological difficulty decision.

## Protocol and implementation differences

The manual, registry, and current source describe different aspects and versions
of the system. The following differences matter when reproducing a session:

| Topic | Study documentation | Current repository |
|---|---|---|
| Session length | Manual p. 32 specifies **20 × 2-minute blocks** | The controller checks for exit after **25 blocks** and relies on game status for block duration; it does not enforce the manual's stopping rule |
| Physiological metric | The registry's intervention description names **RMSSD** | The active analysis computes **ln(HF-HRV)** in eight windows and compares it with two shapelets |
| Personalization inputs | The study describes physiological feedback plus cognitive performance | This controller sends the ECG-derived boolean; it does not implement an accuracy-based decision rule or the full game-side adaptation |
| Follow-up schedule | Registry: baseline, Week 7, and 3 months; manual p. 12: T3 within a 2-week window 8 weeks after T2 | Visit timing is outside this software; these descriptions should not be assumed to be identical |

The instructions below document the code as it currently runs. Confirm the
approved study version and reconcile these differences before treating this
checkout as an exact implementation of the procedure manual.

## How it works

[`ECG_Device_Controller_v2.py`](ECG_Device_Controller_v2.py) is the session entry
point. It resolves the external session ID through the API, discovers a configured
PLUX device, and verifies communication by reading its battery level.

For each block, the controller:

1. Gets the latest block identifier and polls the game's readiness status.
2. Notifies the game that the ECG device is ready and starts acquisition.
3. Records ECG while the game reports that the block is running.
4. Stops acquisition when the block ends and saves the raw ECG samples.
5. Cleans the ECG, extracts eight HF-HRV values, and compares their temporal
   pattern with two reference shapelets.
6. Saves the analysis results locally and sends an `IncreaseDifficulty` boolean
   to the API, then waits for the next block.

The controller's loop is configured for 25 blocks, compared with 20 in the manual
(see [Protocol and implementation differences](#protocol-and-implementation-differences)).
The game application and API are external services; this repository contains the
ECG controller and monitor.

## Adaptive decision logic

[`biosignalHeartpy_v002.py`](biosignalHeartpy_v002.py) computes Spearman rank
correlations between the eight-point ln(HF-HRV) sequence and each reference
pattern, `shapeletA` and `shapeletB`. The controller uses `r_threshold = 0.2`:

| Correlation result | API decision |
|---|---|
| `rho_A >= 0.2` **or** `rho_B >= 0.2` | `IncreaseDifficulty: true` |
| Neither comparison meets the threshold | `IncreaseDifficulty: false` |

The payload also contains the current `BlockIdentifier`. Correlation p-values are
saved to CSV but do not enter this decision. The controller requests an increase;
the game/API applies the resulting level behavior.

## ECG and HF-HRV analysis

The active pipeline in `getHF_HRV(...)` is:

1. Require at least **90 seconds** of ECG at **1,000 Hz**.
2. Convert 16-bit ADC samples to mV using the existing PLUX conversion formula,
   check signal polarity with NeuroKit2, and clean the ECG.
3. Select **eight 30-second windows** across the recording. Their sample stride
   is `(signal_length - window_length) // (num_windows - 1)`; overlap depends
   on the block duration.
4. Detect R-peaks with artifact correction and compute NeuroKit2 HRV metrics in
   each window.
5. Take the natural logarithm of `HRV_HF` and compare the resulting eight-point
   sequence with the shapelets.

Acquisition uses channel mask `0x03` and 16-bit resolution. The existing analysis
reads **CH2** (`raw_signal[2]`, after the sequence-number and CH1 columns).
The monitor follows that same channel. Sampling rate and channel changes require
matching changes to the analysis configuration.

## Repository layout

| Path | Purpose |
|---|---|
| [`ECG_Device_Controller_v2.py`](ECG_Device_Controller_v2.py) | Session driver, device acquisition, API communication, and difficulty decision |
| [`biosignalHeartpy_v002.py`](biosignalHeartpy_v002.py) | ECG cleaning, HF-HRV extraction, shapelet comparison, and CSV output |
| [`ecg_monitor.py`](ecg_monitor.py) | Optional Tkinter waveform and analysis viewer |
| [`PLUX-API-Python3/`](PLUX-API-Python3/) | Bundled native PLUX drivers for different platforms and Python versions |
| [`Start_ECG_Monitor_v2.bat`](Start_ECG_Monitor_v2.bat) | Windows source-checkout launcher with monitoring enabled |
| [`Start_ECG_Recording_v2.bat`](Start_ECG_Recording_v2.bat) | Original Windows recording launcher |
| [`requirements-windows-py310.txt`](requirements-windows-py310.txt) | Direct dependency versions for a fresh Windows Python 3.10 environment |
| [`requirements-windows-py310.lock.txt`](requirements-windows-py310.lock.txt) | Full pinned Windows Python 3.10 dependency set |
| [`packaging/windows/`](packaging/windows/) | Windows distribution templates: setup, launchers, environment check, and instructions |
| [`packaging/build_windows_package.py`](packaging/build_windows_package.py) | Builds and verifies a complete Windows source/driver ZIP |
| [`test_ecg_monitor.py`](test_ecg_monitor.py) | Offline regression checks |
| [`README_UPDATE_WINDOWS.txt`](README_UPDATE_WINDOWS.txt) | Instructions for updating an existing Windows installation |

Experiment CSVs, recordings, logs, virtual environments, and generated archives
are excluded by [`.gitignore`](.gitignore). Runtime outputs remain local.

## Installation

Clone the repository and run commands from its root:

```bash
git clone https://github.com/ymliu17/PSOPT-HMI.git
cd PSOPT-HMI
```

Use a Python interpreter whose **minor version and architecture match a bundled
PLUX driver**. The controller resolves drivers relative to its own file and prints
the selected directory at startup.

| Platform / interpreter | Example driver directory | Setup status |
|---|---|---|
| Windows x64, Python 3.10 | `Win64_310` | Pinned dependencies and distribution tools provided; test acquisition on the target PC |
| Apple Silicon, native arm64 Python 3.11 | `M1_311` | Device connection and battery reading verified on the development Mac |
| Intel Mac, Python 3.10 | `MacOS/Intel310` | Driver bundled; not verified in this setup |
| Linux | `Linux64` selected by the controller | Architecture/ABI compatibility needs checking; ARM driver selection needs adjustment |

Other driver builds are included for existing environments; see
[`PLUX-API-Python3/README.md`](PLUX-API-Python3/README.md).

### Existing working environment

Activate the Python environment already used for PSOPT and keep its working
dependency versions. Configure the new checkout to use the same server, device,
and experiment parameters as the old installation.

The analysis imports NumPy, pandas, SciPy, NeuroKit2, requests, and Matplotlib;
the provided dependency set also includes scikit-learn. Monitoring requires
**Tkinter** in the same interpreter. Check it with:

```bash
python -m tkinter
```

### New Windows environment (Python 3.10 x64)

Install Python 3.10 64-bit with pip, venv, and Tcl/Tk support. From the repository
root, create a dedicated environment:

```bat
py -3.10-64 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-windows-py310.lock.txt
.venv\Scripts\python.exe -m tkinter
```

Use `.venv\Scripts\python.exe` for session commands below, or activate the
environment in your terminal first. The root-level batch launchers use `python`
from the current environment; the launchers in the generated Windows package
automatically select its local `.venv`.

### Apple Silicon (Python 3.11)

Use the existing working Python 3.11 environment:

```bash
python3.11 -m tkinter
python3.11 ECG_Device_Controller_v2.py YOUR_SESSION_ID monitor
```

The Windows lock file targets Windows Python 3.10; a separate macOS lock file is
not provided. macOS must permit the trusted `plux.so` library and its separate
`bth_macprocess` Bluetooth helper to run. See [Troubleshooting](#troubleshooting)
for the helper's execute permission.

## Configuration

Review these constants in
[`ECG_Device_Controller_v2.py`](ECG_Device_Controller_v2.py) before a session:

| Constant | Default / meaning |
|---|---|
| `webserver` | `https://brainwellnessgamesapi.azurewebsites.net` — API base URL |
| `ECG_DEVICES` | Allowed PLUX Bluetooth addresses; replace with your device's address if needed |
| `frequency` | `1000` Hz acquisition rate |
| `code` | `0x03` channel mask; current analysis uses CH2 |
| `r_threshold` | `0.2` correlation threshold for requesting a difficulty increase |
| `requestTime` | `0.5` seconds, used in polling loops; some loops add other delays |

Analysis constants in [`biosignalHeartpy_v002.py`](biosignalHeartpy_v002.py):

| Constant | Default / meaning |
|---|---|
| `fs` | `1000` Hz; must match acquisition |
| `window_length` | `30 * fs` samples per analysis window |
| `num_windows` | `8`, matching the length of each shapelet |
| `min_signal_length` | `90 * fs` samples |
| `shapeletA`, `shapeletB` | Eight-point reference patterns for Spearman comparison |

Use the active dynamic-window settings above when reviewing the algorithm;
the file also retains older windowing utilities.

## Running a session

Command form:

```bash
python ECG_Device_Controller_v2.py <SESSION_EXTERNAL_ID> [monitor]
```

1. Power on and pair the PLUX device. Close other acquisition programs that may
   already be using it.
2. Open the PSOPT [combined-game page](https://brainwellnessgames.azurewebsites.net/Home/Master)
   identified in the manual (p. 40), or your study's configured deployment.
   Create/select the session on the server configured by `webserver`.
3. Start the controller with the **same external session ID** used in the game:

   ```bash
   python ECG_Device_Controller_v2.py 99999 monitor
   ```

4. Look for `Connected to ECG device ...; battery: ...%`, then follow the game's
   block-start flow. The monitor opens when ECG acquisition begins.

For study use, follow the manual's orientation and questionnaire procedures around
these software steps. Between pSOPT blocks, the manual calls for focus, difficulty,
and novelty ratings before the participant starts the next block (p. 41). Those
ratings are collected outside this monitor.

`99999` is an example; use your actual session ID. The controller looks up an
existing server session rather than creating one. A local API must implement the
same session, block, game-status, and device endpoints; this repository does not
include a Docker deployment.

For recording and analysis without the monitor:

```bash
python ECG_Device_Controller_v2.py 99999
```

On Windows, `Start_ECG_Monitor_v2.bat` prompts for the session ID. Run it from an
activated environment, or use the generated Windows package's launchers.

Run from the **repository root** so that the CSV outputs have a predictable
location. On Apple Silicon, use `python3.11` explicitly if that is your configured
interpreter.

## Recorded output

Files are written to the current working directory for each processed block:

```text
ECG_Block_<block-id>_<session-id>.csv             # raw CH2 ADC samples
HF_Block_<block-id>_<session-id>.csv              # eight ln(HF-HRV) values
Rho_Shapelet_A_Block_<block-id>_<session-id>.csv   # rho and p value for A
Rho_Shapelet_B_Block_<block-id>_<session-id>.csv   # rho and p value for B
```

Raw samples are saved before HF-HRV analysis. An analysis failure can therefore
leave the raw CSV without the later result files. The current implementation does
not save the cleaned waveform or a separate decision CSV. The boolean decision is
printed, shown in the monitor when enabled, and sent to the API.

## ECG monitor

Monitoring is **off by default**. Add the literal word `monitor` to the normal
session command; no second controller process is needed.

The separate window shows:

- **ECG waveforms:** the latest five seconds of raw CH2 during acquisition, then
  the complete block's raw ADC signal and cleaned ECG in mV during processing.
- **HF-HRV windows:** the exact start/end times and ln(HF-HRV) values used by the
  analysis, updated as the eight windows finish.
- **Shapelet decision:** the observed HF-HRV trend and both reference patterns,
  the actual Spearman rho values, threshold, `IncreaseDifficulty` decision, and
  API upload status. The view switches to this tab after the first analysis
  window completes.

Waveforms use min/max downsampling for display, and the trend/shapelet comparison
uses display-only standardization. CSV samples and the analysis retain their
original data. The monitor observes the existing results; it does not recalculate
the decision or make API requests.

The completed block remains visible until the next acquisition begins. Closing
the viewer does not stop acquisition or analysis; it reopens at the next block.
The viewer runs in a separate process, and display failures are isolated from the
session workflow. Temporary monitor snapshots are removed when the session exits.
No additional web service is required.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No bundled PLUX driver ...` or native import failure | Match the interpreter's Python minor version and CPU architecture to the driver folder |
| `No module named ...` | Activate the intended environment and install its dependencies |
| Windows `DLL load failed` | Check Python/driver compatibility and the required Microsoft Visual C++ runtime; see the Windows instructions |
| macOS blocks `plux.so` or `bth_macprocess` | Allow the trusted native library and helper in macOS; they are separate binaries |
| macOS `Spawn Status 13` | Check the Bluetooth helper's execute permission |
| Device cannot be found or pairing times out | Check power, pairing, `ECG_DEVICES`, and whether another program is using the device |
| No monitoring window | Include `monitor`, check Tkinter, and wait for actual ECG acquisition to begin |
| Session/API error | Check `webserver`, connectivity, and that the external session ID exists on that server |
| HF-HRV unavailable | Check recording duration and signal quality; the current analysis requires at least 90 seconds |

For the Apple Silicon Python 3.11 helper, restore owner execute permission with:

```bash
chmod u+x PLUX-API-Python3/M1_311/bth_macprocess
```

A native `[BTH macOs] Timeout` message alone does not establish failure: the
controller verifies communication with a battery read before reporting a usable
connection. A failed verification closes the connection and raises the error.
Battery below 10% produces a warning.

See the [PLUX setup guidance](https://github.com/pluxbiosignals/python-samples)
and [Windows instructions](packaging/windows/README_WINDOWS.txt).

## Windows distribution

Create a complete Windows source/driver package for a colleague:

```bash
python packaging/build_windows_package.py --version 2026-11-19
```

The ZIP and its SHA-256 checksum are written to `dist/`. The package includes the
runtime code, Windows x64 drivers, pinned dependencies, an environment checker,
and launchers. It includes no Python installer or preinstalled environment.

After extracting the package into a new folder:

1. Keep an existing working ECG environment, or run `Setup_Environment.bat` with
   Python 3.10 x64 installed to create a local `.venv` and install dependencies.
2. Review the server/device configuration and run `check_windows_environment.py`
   with the intended interpreter. This checks imports without contacting the
   device or API.
3. Run `Start_ECG_Monitor_v2.bat` and enter the game's session ID.

The setup/checker scripts under `packaging/windows/` are **package templates**;
the build places them beside the runtime code at the ZIP's root. For a Git clone,
use the manual environment commands in [Installation](#installation).

The build uses an explicit file list, verifies the extracted files against a
SHA-256 manifest, and runs the offline regression suite. See the complete
[Windows package instructions](packaging/windows/README_WINDOWS.txt).

## Validation and current limitations

Run the offline suite without a device or API connection:

```bash
python -m unittest -v test_ecg_monitor.py
```

The 13 regression checks cover monitor behavior and failure isolation, driver
selection, the native device constructor contract, connection verification, and
the mocked session workflow. They do not replace acquisition tests on the target
hardware. macOS device connection/battery reading has been verified; Windows
Bluetooth acquisition still needs validation on the receiving PC.

Current controller limitations:

- The study's 20-block stopping rule and registered RMSSD description differ from
  this checkout; see [Protocol and implementation differences](#protocol-and-implementation-differences).
- Short recordings return no HF-HRV values, but downstream code has no safe
  short-block fallback and may exit. A monitor label of unavailable does not
  provide a substitute decision.
- Device selection checks only the first discovered device entry against
  `ECG_DEVICES`; discovery order can matter when several devices are present.
- API polling has no overall timeout. The loop also waits for game readiness
  before its 25-block exit check, so a completed session can remain waiting.

## Third-party files

PLUX native binaries are supplied with the existing project and originate from
the [PLUX Python samples project](https://github.com/pluxbiosignals/python-samples).
See the [upstream license copy](packaging/windows/third_party/PLUX-python-samples-LICENSE.txt)
and [provenance](packaging/windows/third_party/PLUX-SOURCE.txt). That upstream
license file is not a new license grant for this project's application code.
