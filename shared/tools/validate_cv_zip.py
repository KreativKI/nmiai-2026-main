#!/usr/bin/env python3
"""
NM i AI 2026 — CV Submission ZIP Validator (shared/tools/validate_cv_zip.py)

Validates a NorgesGruppen object detection submission ZIP before uploading.
Checks: structure, blocked imports, weight sizes, file counts, run.py contract.

Usage:
    python3 shared/tools/validate_cv_zip.py path/to/submission.zip
    python3 shared/tools/validate_cv_zip.py path/to/submission.zip --json  # JSON output for dashboard

Output: PASS/FAIL with details. --json outputs structured JSON for the dashboard.
"""

import argparse
import ast
import json
import re
import sys
import zipfile
from pathlib import Path

BLOCKED_MODULES = [
    "os", "sys", "subprocess", "socket", "ctypes", "builtins", "importlib",
    "pickle", "marshal", "shelve", "shutil",
    "yaml", "requests", "urllib", "http.client",
    "multiprocessing", "threading", "signal", "gc",
    "code", "codeop", "pty",
]

BLOCKED_CALLS = ["eval(", "exec(", "compile(", "__import__("]
BLOCKED_SET = set(BLOCKED_MODULES)

WEIGHT_EXTENSIONS = {".pt", ".pth", ".onnx", ".safetensors", ".npy", ".npz"}
ALLOWED_EXTENSIONS = {".py", ".json", ".yaml", ".yml", ".cfg"} | WEIGHT_EXTENSIONS

MAX_ZIP_SIZE_MB = 420
MAX_WEIGHT_SIZE_MB = 420
MAX_PY_FILES = 10
MAX_WEIGHT_FILES = 3
MAX_TOTAL_FILES = 1000


def validate_zip(zip_path: str) -> dict:
    """Validate a CV submission ZIP. Returns structured result dict."""
    result = {
        "path": zip_path,
        "valid": True,
        "errors": [],
        "warnings": [],
        "files": [],
        "stats": {},
    }

    path = Path(zip_path)
    if not path.exists():
        result["valid"] = False
        result["errors"].append(f"File not found: {zip_path}")
        return result

    if not zipfile.is_zipfile(str(path)):
        result["valid"] = False
        result["errors"].append("Not a valid ZIP file")
        return result

    with zipfile.ZipFile(str(path), "r") as zf:
        names = zf.namelist()
        infos = zf.infolist()

        total_size = 0
        weight_size_raw = 0
        py_files = []
        weight_files = []

        for info in infos:
            if info.is_dir():
                continue
            name = info.filename
            size_mb = info.file_size / (1024 * 1024)
            total_size += info.file_size
            ext = Path(name).suffix.lower()

            entry = {"name": name, "size_mb": round(size_mb, 2), "ext": ext}
            result["files"].append(entry)

            if ext == ".py":
                py_files.append(entry)
            elif ext in WEIGHT_EXTENSIONS:
                weight_files.append(entry)
                weight_size_raw += info.file_size

        total_size_mb = total_size / (1024 * 1024)
        weight_total_mb = weight_size_raw / (1024 * 1024)

        result["stats"] = {
            "total_files": len(result["files"]),
            "py_files": len(py_files),
            "weight_files": len(weight_files),
            "total_size_mb": round(total_size_mb, 2),
            "weight_size_mb": round(weight_total_mb, 2),
        }

        # Check 1: run.py at root
        if "run.py" not in names:
            nested = [n for n in names if n.endswith("run.py")]
            if nested:
                result["valid"] = False
                result["errors"].append(f"run.py not at root. Found: {nested[0]} (nested in subfolder)")
            else:
                result["valid"] = False
                result["errors"].append("run.py not found in ZIP")

        # Check 2: file counts
        if len(py_files) > MAX_PY_FILES:
            result["valid"] = False
            result["errors"].append(f"Too many .py files: {len(py_files)} (max {MAX_PY_FILES})")

        if len(weight_files) > MAX_WEIGHT_FILES:
            result["valid"] = False
            result["errors"].append(f"Too many weight files: {len(weight_files)} (max {MAX_WEIGHT_FILES})")

        if len(result["files"]) > MAX_TOTAL_FILES:
            result["valid"] = False
            result["errors"].append(f"Too many files: {len(result['files'])} (max {MAX_TOTAL_FILES})")

        # Check 3: sizes
        if total_size_mb > MAX_ZIP_SIZE_MB:
            result["valid"] = False
            result["errors"].append(f"ZIP too large: {total_size_mb:.1f} MB (max {MAX_ZIP_SIZE_MB} MB)")

        if weight_total_mb > MAX_WEIGHT_SIZE_MB:
            result["valid"] = False
            result["errors"].append(f"Weights too large: {weight_total_mb:.1f} MB (max {MAX_WEIGHT_SIZE_MB} MB)")

        # Check 4: blocked imports in .py files (AST-based + regex fallback)
        for py_file in py_files:
            try:
                content = zf.read(py_file["name"]).decode("utf-8", errors="replace")
            except Exception:
                result["warnings"].append(f"Could not read {py_file['name']}")
                continue

            # Try AST parsing first (ignores docstrings, handles multi-import)
            ast_checked = False
            try:
                tree = ast.parse(content)
                ast_checked = True
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            if top in BLOCKED_SET:
                                result["valid"] = False
                                result["errors"].append(
                                    f"BLOCKED IMPORT in {py_file['name']}:{node.lineno}: import {alias.name}"
                                )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top = node.module.split(".")[0]
                            if top in BLOCKED_SET:
                                result["valid"] = False
                                result["errors"].append(
                                    f"BLOCKED IMPORT in {py_file['name']}:{node.lineno}: from {node.module} import ..."
                                )
            except SyntaxError:
                pass  # Fall back to regex

            # Regex fallback for files that don't parse + blocked calls check
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                # Only regex-check imports if AST parse failed
                if not ast_checked:
                    for mod in BLOCKED_MODULES:
                        patterns = [
                            rf"^import\s+{re.escape(mod)}(\s|$|,|\.)",
                            rf"^from\s+{re.escape(mod)}(\s|\.)",
                        ]
                        for pat in patterns:
                            if re.search(pat, stripped):
                                result["valid"] = False
                                result["errors"].append(
                                    f"BLOCKED IMPORT in {py_file['name']}:{i}: {stripped}"
                                )

                # Always check for blocked calls (eval, exec, etc.)
                for call in BLOCKED_CALLS:
                    if call in stripped:
                        result["valid"] = False
                        result["errors"].append(
                            f"BLOCKED CALL in {py_file['name']}:{i}: {stripped}"
                        )

        # Check 5: disallowed file types
        for f in result["files"]:
            ext = f["ext"]
            if ext and ext not in ALLOWED_EXTENSIONS:
                result["warnings"].append(f"Unusual file type: {f['name']} ({ext})")

        # Check 6: run.py has correct CLI interface
        if "run.py" in names:
            try:
                run_content = zf.read("run.py").decode("utf-8", errors="replace")
                if "--input" not in run_content and "--images" not in run_content:
                    result["warnings"].append("run.py may not accept --input/--images flag")
                if "--output" not in run_content:
                    result["warnings"].append("run.py may not accept --output flag")
            except Exception:
                pass

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate NorgesGruppen CV submission ZIP")
    parser.add_argument("zip_path", help="Path to submission.zip")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", help="Write JSON result to file")
    args = parser.parse_args()

    result = validate_zip(args.zip_path)

    if args.json or args.output:
        output = json.dumps(result, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Result written to {args.output}")
        else:
            print(output)
    else:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"\n{'='*50}")
        print(f"  CV ZIP Validation: {status}")
        print(f"{'='*50}")
        print(f"  File: {result['path']}")
        stats = result["stats"]
        print(f"  Total size: {stats.get('total_size_mb', 0):.1f} MB / {MAX_ZIP_SIZE_MB} MB")
        print(f"  Weight size: {stats.get('weight_size_mb', 0):.1f} MB / {MAX_WEIGHT_SIZE_MB} MB")
        print(f"  Python files: {stats.get('py_files', 0)} / {MAX_PY_FILES}")
        print(f"  Weight files: {stats.get('weight_files', 0)} / {MAX_WEIGHT_FILES}")
        print(f"  Total files: {stats.get('total_files', 0)} / {MAX_TOTAL_FILES}")

        if result["errors"]:
            print(f"\n  ERRORS ({len(result['errors'])}):")
            for e in result["errors"]:
                print(f"    {e}")
        if result["warnings"]:
            print(f"\n  WARNINGS ({len(result['warnings'])}):")
            for w in result["warnings"]:
                print(f"    {w}")
        if not result["errors"] and not result["warnings"]:
            print("\n  All checks passed.")
        print()

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
