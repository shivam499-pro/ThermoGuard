"""
Build a Lambda zip without Docker.

Uses Linux manylinux wheels so the package runs on Amazon Linux even when
this script is executed on Windows.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PACKAGE = DIST / "package"
ZIP_PATH = DIST / "thermoguard.zip"
REQUIREMENTS = ROOT / "requirements-lambda.txt"

COPY_DIRS = ("app", "lambda_handlers", "risk_engine", "data")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    PACKAGE.mkdir(parents=True)

    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS),
            "-t",
            str(PACKAGE),
            "--upgrade",
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--only-binary=:all:",
        ]
    )

    for name in COPY_DIRS:
        src = ROOT / name
        dest = PACKAGE / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in PACKAGE.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE).as_posix())

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {ZIP_PATH} ({size_mb:.1f} MB)")
    if size_mb >= 50:
        raise SystemExit("Zip exceeds the 50 MB Lambda upload limit.")


if __name__ == "__main__":
    main()
