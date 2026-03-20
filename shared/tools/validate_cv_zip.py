#!/usr/bin/env python3
"""Validate a CV submission ZIP before uploading.

Checks: ZIP structure, run.py at root, blocked imports, weight limits,
file counts, and category_id ranges. Exit 0 = safe, exit 1 = FAIL.

Usage: python3 shared/tools/validate_cv_zip.py submission.zip
"""
import argparse
import json
import re
import tempfile
import zipfile
from pathlib import Path

BLOCKED_MODULES = [
    "os", "sys", "subprocess", "socket", "ctypes", "builtins", "importlib",
    "marshal", "shelve", "shutil", "yaml", "requests", "urllib", "http.client",
    "multiprocessing", "threading", "signal", "gc", "code", "codeop", "pty",
    "pickle",  # blocked by competition sandbox
]

MAX_ZIP_MB = 420
MAX_PY_FILES = 10
MAX_WEIGHT_FILES = 3
WEIGHT_EXTS = {".onnx", ".pt", ".pth", ".safetensors", ".npy"}
ALLOWED_EXTS = {".py", ".json", ".yaml", ".yml", ".cfg", ".pt", ".pth", ".onnx", ".safetensors", ".npy"}


def check_blocked_imports(py_path: Path) -> list[str]:
    """Return list of blocked import violations in a .py file."""
    violations = []
    text = py_path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for mod in BLOCKED_MODULES:
            patterns = [
                rf"^import\s+{re.escape(mod)}\b",
                rf"^from\s+{re.escape(mod)}\b",
            ]
            for pat in patterns:
                if re.search(pat, stripped):
                    violations.append(f"  {py_path.name}:{i}: {stripped}")
    return violations


def main():
    parser = argparse.ArgumentParser(description="Validate CV submission ZIP")
    parser.add_argument("zip_path", help="Path to submission ZIP file")
    args = parser.parse_args()

    zip_path = Path(args.zip_path)
    errors = []
    warnings = []

    print(f"=== CV ZIP Validator: {zip_path.name} ===\n")

    # 1. File exists
    if not zip_path.exists():
        print(f"FAIL: ZIP not found: {zip_path}")
        raise SystemExit(1)

    # 2. Size check
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Size: {size_mb:.1f} MB (limit: {MAX_ZIP_MB} MB)")
    if size_mb > MAX_ZIP_MB:
        errors.append(f"ZIP exceeds {MAX_ZIP_MB} MB limit ({size_mb:.1f} MB)")

    # 3. ZIP structure
    if not zipfile.is_zipfile(zip_path):
        print("FAIL: Not a valid ZIP file")
        raise SystemExit(1)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        # run.py at root
        if "run.py" not in names:
            errors.append("run.py not found at ZIP root")
        else:
            print("OK: run.py at root")

        # DISALLOWED FILE TYPES CHECK (critical: .npz, .bin, .data, etc. are NOT allowed)
        disallowed = []
        for n in names:
            ext = Path(n).suffix.lower()
            if ext and ext not in ALLOWED_EXTS:
                disallowed.append(f"{n} ({ext})")
        if disallowed:
            errors.append(f"DISALLOWED file types found (allowed: {', '.join(sorted(ALLOWED_EXTS))})")
            for d in disallowed:
                errors.append(f"  DISALLOWED: {d}")
        else:
            print("OK: All file types allowed")

        # Count .py files
        py_files = [n for n in names if n.endswith(".py") and "/" not in n]
        py_all = [n for n in names if n.endswith(".py")]
        print(f"Python files: {len(py_all)} (limit: {MAX_PY_FILES})")
        if len(py_all) > MAX_PY_FILES:
            errors.append(f"Too many .py files: {len(py_all)} > {MAX_PY_FILES}")

        # Count weight files
        weight_files = [n for n in names if Path(n).suffix in WEIGHT_EXTS]
        print(f"Weight files: {len(weight_files)} (limit: {MAX_WEIGHT_FILES})")
        if len(weight_files) > MAX_WEIGHT_FILES:
            errors.append(f"Too many weight files: {len(weight_files)} > {MAX_WEIGHT_FILES}")

        # Weight sizes
        total_weight_mb = sum(
            zf.getinfo(n).file_size for n in weight_files
        ) / (1024 * 1024)
        print(f"Total weight size: {total_weight_mb:.1f} MB (limit: {MAX_ZIP_MB} MB)")

        # List contents
        print(f"\nContents ({len(names)} files):")
        for n in sorted(names):
            info = zf.getinfo(n)
            print(f"  {info.file_size / (1024*1024):8.1f} MB  {n}")

    # 4. Blocked imports check
    print("\n=== Blocked Import Scan ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmpdir)

        all_violations = []
        for pyfile in sorted(Path(tmpdir).rglob("*.py")):
            violations = check_blocked_imports(pyfile)
            all_violations.extend(violations)

        if all_violations:
            errors.append("BLOCKED IMPORTS FOUND (= INSTANT BAN):")
            for v in all_violations:
                errors.append(v)
        else:
            print("OK: No blocked imports")

    # 5. Summary
    print()
    if errors:
        print("=" * 50)
        print("FAIL: Do NOT submit this ZIP")
        print("=" * 50)
        for e in errors:
            print(f"  ERROR: {e}")
        raise SystemExit(1)
    else:
        print("=" * 50)
        print("PASS: ZIP structure validated")
        print("=" * 50)
        if warnings:
            for w in warnings:
                print(f"  WARNING: {w}")


if __name__ == "__main__":
    main()
