"""Build a Windows source/driver distribution from an explicit allowlist."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "ECG_Device_Controller_v2.py", "biosignalHeartpy_v002.py", "ecg_monitor.py",
    "test_ecg_monitor.py", "requirements-windows-py310.txt",
    "requirements-windows-py310.lock.txt",
)
WINDOWS = (
    "Start_ECG_Monitor_v2.bat", "Start_ECG_Recording_v2.bat",
    "Setup_Environment.bat", "check_windows_environment.py", "README_WINDOWS.txt",
    "third_party/PLUX-python-samples-LICENSE.txt", "third_party/PLUX-SOURCE.txt",
)
DRIVERS = ("Win64_37", "Win64_38", "Win64_39", "Win64_310")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release identifier, e.g. 2026-11-18")
    args = parser.parse_args()
    if not args.version or any(c not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-_" for c in args.version):
        parser.error("Invalid version")
    name = "PSOPT-HMI-Windows-Full-" + args.version
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    target = output / (name + ".zip")
    sources = {relative: ROOT / relative for relative in RUNTIME}
    sources.update({relative: ROOT / "packaging/windows" / relative for relative in WINDOWS})
    for folder in DRIVERS:
        directory = ROOT / "PLUX-API-Python3" / folder
        if not (directory / "plux.pyd").is_file():
            raise FileNotFoundError(directory / "plux.pyd")
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in (".dll", ".pyd"):
                sources[path.relative_to(ROOT).as_posix()] = path
    with tempfile.TemporaryDirectory(prefix="psopt-windows-package-") as temp:
        stage = Path(temp) / name
        for relative, source in sources.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == ".bat":
                destination.write_bytes(source.read_text().replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
            else:
                shutil.copy2(source, destination)
        manifest = "".join(
            hashlib.sha256((stage / relative).read_bytes()).hexdigest() + "  " + relative + "\n"
            for relative in sorted(sources)
        )
        (stage / "MANIFEST_SHA256.txt").write_text(manifest, encoding="utf-8")
        names = sorted(sources) + ["MANIFEST_SHA256.txt"]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in names:
                archive.write(stage / relative, name + "/" + relative)
        extracted = Path(temp) / "extracted"
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {name + "/" + relative for relative in names}
            archive.extractall(extracted)
        package = extracted / name
        for line in (package / "MANIFEST_SHA256.txt").read_text().splitlines():
            digest, relative = line.split("  ", 1)
            assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == digest
        subprocess.run([sys.executable, "-m", "unittest", "-q", "test_ecg_monitor.py"], cwd=package, check=True)
        for relative in RUNTIME[:3]:
            assert (package / relative).read_bytes() == (ROOT / relative).read_bytes()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(digest + "  " + target.name + "\n", encoding="utf-8")
    print("Archive:", target)
    print("Files:", len(names))
    print("Size: {:.2f} MiB".format(target.stat().st_size / (1024 * 1024)))
    print("SHA256:", digest)


if __name__ == "__main__":
    main()
