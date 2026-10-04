"""Execute only the packaged lesson runner, never source paths from imported traces."""
from pathlib import Path
import hashlib
import shutil
import subprocess
from .core import ROOT, LESSONS, TraceError, parse_trace

SOURCE = ROOT / "java" / "PatternPilot.java"

def source_hash():
    return hashlib.sha256(SOURCE.read_bytes()).hexdigest()

def run_java(lesson: str, variant="normal", value=100):
    if lesson not in LESSONS or variant not in ("normal", "broken"):
        raise TraceError("未知の教材またはvariantです。")
    if type(value) is not int or not 0 <= value <= 10000:
        raise TraceError("入力は0〜10000の整数です。")
    java = shutil.which("java")
    if not java: raise RuntimeError("Javaが見つかりません。JDK 17以降を導入するか、同梱記録を再生してください。")
    command = [java, "-Xmx128m", "-Dfile.encoding=UTF-8", str(SOURCE), lesson, variant, str(value)]
    try:
        r = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=25, cwd=ROOT)
    except subprocess.TimeoutExpired as ex:
        raise RuntimeError("Java実行が25秒を超えたため停止しました。") from ex
    if r.returncode: raise RuntimeError("Java実行に失敗しました:\n" + r.stderr[-3000:])
    events = parse_trace(r.stdout)
    events[0]["source_sha256"] = source_hash()
    events[0]["producer"] = "PatternPilot Java / manual instrumentation v0.1"
    return events
