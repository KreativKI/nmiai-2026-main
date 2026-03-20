"""Check Python files for blocked imports that would cause instant ban."""
import re
from pathlib import Path

# These modules are BLOCKED in the competition sandbox.
# Importing any of them = instant account ban.
BLOCKED_MODULES = [
    "os", "sys", "subprocess", "socket", "multiprocessing",
    "threading", "signal", "shutil", "ctypes", "builtins",
    "importlib", "marshal", "shelve", "code", "codeop",
    "pty", "requests", "urllib",
]

def check_file(filepath: Path) -> list[str]:
    """Return list of violation descriptions found in a file."""
    violations = []
    text = filepath.read_text(encoding="utf-8", errors="replace")

    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue

        for mod in BLOCKED_MODULES:
            # Match: import os, from os import ..., import os.path
            patterns = [
                rf"^import\s+{re.escape(mod)}(\s|$|,|\.)",
                rf"^from\s+{re.escape(mod)}(\s|\.)",
            ]
            for pat in patterns:
                if re.search(pat, stripped):
                    violations.append(f"  {filepath.name}:{i}: {stripped}")
    return violations


def main(directory: str) -> int:
    root = Path(directory)
    all_violations = []

    for pyfile in sorted(root.glob("*.py")):
        violations = check_file(pyfile)
        all_violations.extend(violations)

    if all_violations:
        print("BLOCKED IMPORTS FOUND:")
        for v in all_violations:
            print(v)
        return 1

    print("OK: No blocked imports found")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="Directory containing .py files to check")
    args = parser.parse_args()
    exit(main(args.directory))
