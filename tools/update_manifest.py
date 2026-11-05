"""Check or refresh SHA-256 for tracked working-tree files (requires Git)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="stage additions/deletions first")
    mode.add_argument("--check", action="store_true", help="read-only check (default)")
    args = parser.parse_args()
    try:
        names = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached"], cwd=ROOT
        ).decode("utf-8").split("\0")
        actual = {}
        for name in sorted(set(names) - {"", MANIFEST.name}):
            path = ROOT / name
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"Not a regular tracked file: {name}; stage deletions first")
            actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if args.write:
            MANIFEST.write_text(
                json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Wrote {len(actual)} file hashes to {MANIFEST.name}")
            return 0
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        missing = sorted(set(actual) - set(expected))
        stale = sorted(set(expected) - set(actual))
        changed = sorted(k for k in actual.keys() & expected.keys() if actual[k] != expected[k])
        if missing or stale or changed:
            print(json.dumps({"missing_entries": missing, "stale_entries": stale,
                              "changed_files": changed}, ensure_ascii=False, indent=2))
            return 1
        print(f"PASS: {len(actual)} tracked file hashes match {MANIFEST.name}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
