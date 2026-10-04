import argparse
import json
from pathlib import Path
from .core import ROOT, LESSONS, load_trace, save_trace, summary

def main():
    ap = argparse.ArgumentParser(description="Java OOP Pattern Lab pilot")
    ap.add_argument("--validate", type=Path, help="GUIを起動せず記録を検証")
    ap.add_argument("--regenerate", action="store_true", help="同梱8記録をJavaで再生成")
    ap.add_argument("--screenshot", type=Path, help="GUI確認用PNG")
    args = ap.parse_args()
    if args.validate:
        print(json.dumps(summary(load_trace(args.validate)), ensure_ascii=False, indent=2)); return
    if args.regenerate:
        from .runner import run_java
        for lesson in LESSONS:
            for variant in ("normal", "broken"):
                path = ROOT / "traces" / f"{lesson}_{variant}.jsonl"
                save_trace(run_java(lesson, variant), path)
                print(path.name)
        return
    try:
        from .gui import launch
    except ImportError as ex:
        raise SystemExit("GUIにはPyQt6が必要です。python -m pip install -r requirements.txt\n" + str(ex))
    launch(args.screenshot)

if __name__ == "__main__": main()
