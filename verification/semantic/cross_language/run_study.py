"""Run both actual implementations, compare observations, and retain provenance."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


EXPECTED = {
    "decimal": (256, 0, 0, 256),
    "hex": (256, 0, 0, 256),
    "mixed": (10, 90, 156, 0),
    "wrong_family": (256, 0, 0, 0),
    "faulty_hex": (0, 256, 0, 256),
}


def execute(command: list[str]) -> tuple[list[dict], str]:
    p = subprocess.run(command, text=True, capture_output=True, check=True, timeout=120)
    return [json.loads(line) for line in p.stdout.splitlines() if line], p.stdout


def normalize(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "raw_error"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", default=shutil.which("java"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results")
    args = parser.parse_args()
    if not args.java:
        parser.error("A JDK 17+ java executable is required")
    here = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=True)
    executions = {}
    for language, cmd in [
        ("java", [args.java, str(here / "CodecStudy.java")]),
        ("python", [sys.executable, str(here / "codec_study.py")]),
    ]:
        rows, raw = execute(cmd)
        executions[language] = rows
        (args.output / f"{language}.jsonl").write_text(raw, encoding="utf-8")
    summary = []
    for language, rows in executions.items():
        for case, expected in EXPECTED.items():
            trials = [r for r in rows if r.get("case") == case]
            assert sorted(r["x"] for r in trials) == list(range(256))
            ok = sum(r["error"] is None and r["decoded"] == r["x"] for r in trials)
            wrong = sum(r["error"] is None and r["decoded"] != r["x"] for r in trials)
            errors = sum(r["error"] is not None for r in trials)
            family_ok = sum(r["requested"] == r["encoder_family"] == r["decoder_family"]
                            for r in trials)
            assert (ok, wrong, errors, family_ok) == expected, (language, case)
            summary.append(dict(language=language, case=case, roundtrip_ok=ok,
                                wrong_value=wrong, parse_error=errors, family_ok=family_ok))
    j = [normalize(r) for r in executions["java"] if r["kind"] != "boundary"]
    p = [normalize(r) for r in executions["python"] if r["kind"] != "boundary"]
    assert j == p, "A normalized per-input Java/Python observation differs"
    boundaries = {lang: next(r for r in rows if r["kind"] == "boundary")
                  for lang, rows in executions.items()}
    assert boundaries["java"]["negative_division"] == 0
    assert boundaries["python"]["negative_division"] == -1
    assert boundaries["java"]["max_plus_one"] == -2147483648
    assert boundaries["python"]["max_plus_one"] == 2147483648
    assert all(r["value_equal"] and not r["same_identity"] for r in boundaries.values())
    for lang, rows in executions.items():
        for r in rows:
            if r["kind"] == "conversion":
                assert r["decimal"] == str(r["x"])
                assert r["hex"] == format(r["x"], "x")
    versions = subprocess.run([args.java, "-version"], text=True, capture_output=True, check=True)
    result = dict(
        scope="D={0,...,255}; canonical decimal/lowercase hex; standalone pure codec operations",
        trial_executions=2560, paired_trials=1280, paired_conversions=256,
        all_normalized_observations_equal=True,
        exception_abstraction={"java": "NumberFormatException -> ParseError",
                               "python": "ValueError -> ParseError"},
        summary=summary, numeric_and_identity_boundaries=boundaries,
        python=platform.python_version(), platform=platform.platform(),
        java_version=(versions.stderr or versions.stdout).strip(),
        source_sha256={name: hashlib.sha256((here / name).read_bytes()).hexdigest()
                       for name in ["CodecStudy.java", "codec_study.py", "run_study.py"]},
    )
    (args.output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
