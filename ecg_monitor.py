"""Optional local ECG viewer; observation never changes acquisition or decisions.

Only the controller's main thread publishes snapshots. A separate process owns
Tk, so acquisition callbacks never do GUI work or write monitor files.
"""

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


_active_monitor = None


def publish(event, **data):
    if _active_monitor is not None:
        try:
            _active_monitor.update(event, **data)
        except Exception as exc:
            print(f"[ECG monitor] Display update failed: {exc}")


def _finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


def _curve(values, frequency, offset=0, max_points=1200):
    """Bound display size with ordered min/max pairs, preserving narrow peaks."""
    result = []
    size = max(1, math.ceil(len(values) / (max_points // 2)))
    for start in range(0, len(values), size):
        bucket = [(i, _finite(values[i])) for i in range(start, min(start + size, len(values)))]
        valid = [(i, value) for i, value in bucket if value is not None]
        if len(valid) != len(bucket):
            result.append([(offset + start) / frequency, None])
        elif valid:
            low = min(valid, key=lambda point: point[1])
            high = max(valid, key=lambda point: point[1])
            for i, value in sorted(set((low, high))):
                result.append([(offset + i) / frequency, value])
    return result


class _SnapshotMonitor:
    def __init__(self, state_path, session_id, open_on_block=False):
        self.state_path = Path(state_path)
        self.session_id = session_id
        self.open_on_block = open_on_block
        self.process = None
        self.state = {"session": session_id, "status": "Waiting for acquisition", "windows": []}
        self._save()

    def _save(self):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, allow_nan=False), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def update(self, event, **data):
        if self.process is not None and self.process.poll() is not None and event != "begin":
            return
        if event == "begin":
            self.state = {
                "session": self.session_id, "block": str(data["block"]),
                "number": data["number"], "frequency": data["frequency"],
                "threshold": float(data["threshold"]), "status": "Recording ECG",
                "shapelet_a": [float(v) for v in data["shapelet_a"]],
                "shapelet_b": [float(v) for v in data["shapelet_b"]],
                "windows": [], "samples": 0, "duration": 0,
            }
        elif event == "samples":
            rows = data["rows"]
            count = len(rows)
            frequency = self.state["frequency"]
            start = max(0, count - int(5 * frequency))
            # Match raw_signal[2] in the controller: second acquired channel.
            values = [row[2] for row in rows[start:count]]
            self.state.update(samples=count, duration=count / frequency,
                              raw=_curve(values, frequency, start), raw_label="Raw ECG / CH2 (ADC) - latest 5 s")
        elif event == "processing":
            raw = data["raw"]
            self.state.update(status="Cleaning ECG / computing HF-HRV", samples=len(raw),
                              duration=len(raw) / self.state["frequency"],
                              raw=_curve(raw, self.state["frequency"]),
                              raw_label="Raw ECG / CH2 (ADC) - complete block")
        elif event == "cleaned":
            self.state["cleaned"] = _curve(data["signal"], self.state["frequency"])
        elif event == "window":
            self.state["windows"].append({
                "index": data["index"], "start": float(data["start"]),
                "end": float(data["end"]), "hf": _finite(data["hf"]),
            })
            self.state["status"] = f"Computing HF-HRV: {len(self.state['windows'])}/8 windows"
        elif event == "result":
            self.state.update(rho_a=_finite(data["rho_a"]), rho_b=_finite(data["rho_b"]),
                              increase=bool(data["increase"]), status="Block computation complete; uploading result")
        elif event == "upload":
            self.state["status"] = ("Result uploaded; waiting for next block" if data["success"]
                                    else f"Result upload failed (HTTP {data['status_code']})")
        elif event in ("unavailable", "error"):
            self.state["status"] = data["message"]
            self.state["unavailable"] = data["message"]
        else:
            raise ValueError(f"Unknown monitor event: {event}")
        self._save()
        if event == "begin" and self.open_on_block and (self.process is None or self.process.poll() is not None):
            self.process = subprocess.Popen([
                sys.executable, str(Path(__file__).resolve()), "--viewer", str(self.state_path)
            ])


@contextmanager
def enabled_monitor(session_id):
    global _active_monitor
    previous = _active_monitor
    monitor = directory = None
    try:
        try:
            directory = tempfile.TemporaryDirectory(prefix="psopt-ecg-monitor-")
            monitor = _SnapshotMonitor(Path(directory.name) / "state.json", session_id, open_on_block=True)
            _active_monitor = monitor
        except Exception as exc:
            print(f"[ECG monitor] Viewer unavailable; session continues: {exc}")
        yield
    finally:
        _active_monitor = previous
        try:
            process = monitor.process if monitor is not None else None
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        except Exception as exc:
            print(f"[ECG monitor] Viewer cleanup failed: {exc}")
        finally:
            if directory is not None:
                try:
                    directory.cleanup()
                except OSError as exc:
                    print(f"[ECG monitor] Temporary file cleanup failed: {exc}")


def _number(value):
    return "Unavailable" if value is None else f"{value:.4f}"


def result_text(state):
    if "increase" not in state:
        return "Decision: unavailable" if "unavailable" in state else "Decision: pending"
    decision = "Increase difficulty" if state["increase"] else "Do not increase difficulty"
    return (f"{decision}  |  rho A: {_number(state['rho_a'])}  |  rho B: {_number(state['rho_b'])}"
            f"  |  threshold: {state['threshold']:g}")


def _standardize(values):
    if not values or any(value is None for value in values):
        return [None] * len(values)
    mean = sum(values) / len(values)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    return [(value - mean) / deviation if deviation else 0.0 for value in values]


def _draw_chart(canvas, title, series, x_label):
    canvas.delete("all")
    width, height = max(canvas.winfo_width(), 400), max(canvas.winfo_height(), 100)
    left, right, top, bottom = 75, width - 20, 32, height - 34
    canvas.create_text(12, 13, text=title, fill="#dce5ef", anchor="w", font=("Arial", 11, "bold"))
    points = [p for _, curve in series for p in curve if p[1] is not None]
    if not points:
        canvas.create_text(width / 2, height / 2, text="Waiting for data / unavailable", fill="#9baabd")
        return
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    if xmin == xmax:
        xmax = xmin + 1
    pad = (ymax - ymin) * 0.12 or 1
    ymin, ymax = ymin - pad, ymax + pad
    for i in range(4):
        fraction = i / 3
        y = top + (bottom - top) * fraction
        canvas.create_line(left, y, right, y, fill="#26364a")
        canvas.create_text(left - 8, y, text=f"{ymax - fraction * (ymax - ymin):.3g}", fill="#9baabd", anchor="e")
    for i in range(5):
        fraction = i / 4
        x = left + (right - left) * fraction
        canvas.create_text(x, bottom + 12, text=f"{xmin + fraction * (xmax - xmin):.2f}", fill="#9baabd")
    canvas.create_text((left + right) / 2, height - 6, text=x_label, fill="#9baabd")
    for color, curve in series:
        segment = []

        def flush():
            if len(segment) >= 4:
                canvas.create_line(*segment, fill=color, width=1.5)
            elif segment:
                x, y = segment
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)

        for xvalue, yvalue in curve:
            if yvalue is None:
                flush()
                segment = []
                continue
            x = left + (xvalue - xmin) / (xmax - xmin) * (right - left)
            y = bottom - (yvalue - ymin) / (ymax - ymin) * (bottom - top)
            segment.extend((x, y))
        flush()


def _run_viewer(state_path):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("PSOPT HMI - ECG monitor")
    root.geometry("1080x860")
    root.minsize(760, 680)
    title = ttk.Label(root, font=("Arial", 15, "bold"), padding=(12, 10))
    title.pack(anchor="w")
    status = ttk.Label(root, padding=(12, 0, 12, 6), wraplength=1000)
    status.pack(anchor="w")
    summary = ttk.Label(root, font=("Arial", 12, "bold"), padding=(12, 0, 12, 8), wraplength=1000)
    summary.pack(anchor="w")
    ttk.Label(root, text="Rule: increase if rho A OR rho B >= threshold. Closing this window keeps the session running; it reopens next block.",
              padding=(12, 0, 12, 8), wraplength=1000).pack(anchor="w")
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    wave_tab, analysis_tab = ttk.Frame(tabs), ttk.Frame(tabs)
    tabs.add(wave_tab, text="ECG waveforms")
    tabs.add(analysis_tab, text="HF-HRV / shapelet decision")
    raw = tk.Canvas(wave_tab, background="#111c2b", highlightthickness=0)
    raw.pack(fill="both", expand=True, pady=(0, 6))
    cleaned = tk.Canvas(wave_tab, background="#111c2b", highlightthickness=0)
    cleaned.pack(fill="both", expand=True)
    ttk.Label(wave_tab, text="CH2 is the channel used by the controller. Waveforms are reduced for display; analysis uses the full signal.",
              padding=8, wraplength=1000).pack(anchor="w")
    hf = tk.Canvas(analysis_tab, background="#111c2b", highlightthickness=0, height=160)
    hf.pack(fill="both", expand=True, pady=(0, 6))
    shapes = tk.Canvas(analysis_tab, background="#111c2b", highlightthickness=0, height=160)
    shapes.pack(fill="both", expand=True)
    ttk.Label(analysis_tab, text="Shape comparison: ECG trend (green), A (orange), B (blue). Z-scores are for display only; rho uses the existing Spearman calculation.",
              padding=8, wraplength=1000).pack(anchor="w")
    table = ttk.Treeview(analysis_tab, columns=("window", "start", "end", "hf"), show="headings", height=8)
    for column, label in zip(("window", "start", "end", "hf"), ("Window", "Start (s)", "End (s)", "ln(HF-HRV)")):
        table.heading(column, text=label)
        table.column(column, width=150, anchor="center")
    table.pack(fill="x", pady=(0, 6))
    state, last_stamp, last_phase = {}, None, None

    def draw(event=None):
        _draw_chart(raw, state.get("raw_label", "Raw ECG / CH2 (ADC)"), [("#58ddac", state.get("raw", []))], "Time from block start (s)")
        _draw_chart(cleaned, "Cleaned ECG (mV) - complete block", [("#6ebaff", state.get("cleaned", []))], "Time from block start (s)")
        windows = state.get("windows", [])
        _draw_chart(hf, "ln(HF-HRV) - analysis windows", [("#58ddac", [(w["index"] + 1, w["hf"]) for w in windows])], "Window")
        # A partial vector must not look like the completed shapelet comparison.
        values = [w["hf"] for w in windows] if len(windows) == 8 else []
        curves = [("#58ddac", list(enumerate(_standardize(values), 1)))]
        curves += [(color, list(enumerate(_standardize(state.get(key, [])), 1)))
                   for color, key in (("#f6b55c", "shapelet_a"), ("#6ebaff", "shapelet_b"))]
        _draw_chart(shapes, "Shape comparison (z-score)", curves, "Window")

    for canvas in (raw, cleaned, hf, shapes):
        canvas.bind("<Configure>", draw)

    def refresh():
        nonlocal state, last_stamp, last_phase
        try:
            path = Path(state_path)
            stamp = path.stat().st_mtime_ns
            if stamp != last_stamp:
                state = json.loads(path.read_text(encoding="utf-8"))
                title.configure(text=f"Session {state['session']}  |  Block {state.get('number', '-')}  |  {state.get('block', '')}")
                status.configure(text=f"{state['status']}  |  {state.get('samples', 0):,} samples  |  {state.get('duration', 0):.1f} s")
                summary.configure(text=result_text(state))
                for item in table.get_children():
                    table.delete(item)
                for w in state["windows"]:
                    table.insert("", "end", values=(w["index"] + 1, f"{w['start']:.3f}", f"{w['end']:.3f}", _number(w["hf"])))
                phase = (state.get("block"), bool(state.get("windows")))
                if phase != last_phase:
                    tabs.select(analysis_tab if phase[1] else wave_tab)
                last_phase = phase
                draw()
                last_stamp = stamp
        except FileNotFoundError:
            root.destroy()
            return
        except Exception as exc:
            status.configure(text=f"Display update unavailable: {exc}")
        root.after(200, refresh)

    root.after(0, refresh)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--viewer":
        raise SystemExit("Run: python ECG_Device_Controller_v2.py SESSION_ID monitor")
    try:
        _run_viewer(sys.argv[2])
    except Exception as exc:
        print(f"[ECG monitor] Viewer unavailable; session continues: {exc}", file=sys.stderr)
