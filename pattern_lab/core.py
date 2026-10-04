"""Bounded trace format, replay and evidence-based checks. Standard library only."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import Counter
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ("references", "strategy", "state", "observer")
KINDS = {"meta", "new", "set", "call", "return", "checkpoint", "result", "end", "cycle_begin", "cycle_end"}
MAX_BYTES, MAX_EVENTS = 5_000_000, 20_000

class TraceError(ValueError):
    pass

@dataclass
class Finding:
    category: str
    status: str
    title: str
    detail: str
    evidence: list[int] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

@dataclass
class ReplayState:
    objects: dict = field(default_factory=dict)
    last_call: dict | None = None
    result: dict | None = None
    event: dict | None = None

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def load_trace(path: str | Path) -> list[dict]:
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise TraceError("記録ファイルは5 MB以内にしてください。")
    return parse_trace(p.read_text(encoding="utf-8"))


def parse_trace(text: str) -> list[dict]:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise TraceError("記録ファイルが大きすぎます。")
    try:
        events = [json.loads(s) for s in text.splitlines() if s.strip()]
    except (json.JSONDecodeError, RecursionError) as ex:
        raise TraceError(f"JSONを読み込めません: {ex}") from ex
    validate(events)
    return events


def validate(events: list[dict]):
    if not 1 <= len(events) <= MAX_EVENTS:
        raise TraceError("イベント数が範囲外です。")
    if not isinstance(events[0], dict) or events[0].get("kind") != "meta":
        raise TraceError("先頭にmetaイベントが必要です。")
    meta = events[0]
    if type(meta.get("schema")) is not int or meta["schema"] != 1 or meta.get("lesson") not in LESSONS:
        raise TraceError("未対応のスキーマまたは教材です。")
    if meta.get("variant") not in ("normal", "broken"):
        raise TraceError("未対応のvariantです。")
    if type(meta.get("input")) is not int or not 0 <= meta["input"] <= 10000:
        raise TraceError("入力は0〜10000の整数です。")
    required = {
        "new": {"id": str, "type": str, "fields": dict},
        "set": {"id": str, "field": str},
        "call": {"from": str, "to": str, "method": str, "arg": int},
        "return": {"from": str, "value": int},
        "checkpoint": {"name": str, "observed": dict},
        "result": {"value": dict}, "end": {"complete": bool},
        "cycle_begin": {"cycle": str, "members": list, "input": int},
        "cycle_end": {"cycle": str},
    }
    ids, fields, ended = set(), {}, False
    def value_ok(v, depth=0):
        if depth > 12: raise TraceError("入れ子が深すぎます。")
        if v is None or type(v) in (str, bool, int): return
        if isinstance(v, list):
            for x in v: value_ok(x, depth+1)
            return
        if isinstance(v, dict) and set(v) == {"ref"} and isinstance(v["ref"], str) and v["ref"] in ids: return
        raise TraceError("未対応の値、または未生成オブジェクトへの参照です。")
    for n, e in enumerate(events, 1):
        if not isinstance(e, dict) or type(e.get("seq")) is not int or e["seq"] != n or e.get("kind") not in KINDS:
            raise TraceError(f"イベント{n}: 連番または種別が不正です。")
        if type(e.get("line")) is not int or e["line"] < 0 or ended:
            raise TraceError(f"イベント{n}: 行番号または終了位置が不正です。")
        k = e["kind"]
        if k == "meta" and n != 1: raise TraceError("metaが重複しています。")
        for name, typ in required.get(k, {}).items():
            if type(e.get(name)) is not typ: raise TraceError(f"イベント{n}: {name}が不正です。")
        if k == "new":
            if e["id"] in ids or not e["id"]: raise TraceError("重複したオブジェクトIDです。")
            ids.add(e["id"]); fields[e["id"]] = set(e["fields"])
            for v in e["fields"].values(): value_ok(v)
        if k == "set":
            if e["id"] not in ids or e["field"] not in fields[e["id"]] or "value" not in e:
                raise TraceError("未定義のオブジェクトまたはフィールドです。")
            value_ok(e["value"])
        if k in ("call", "return"):
            for f in (("from", "to") if k == "call" else ("from",)):
                if e[f] not in ids: raise TraceError("呼び出し対象が未生成です。")
        if k == "cycle_begin": value_ok(e["members"])
        if k == "end": ended = True


def step(state: ReplayState, event: dict) -> None:
    k = event["kind"]
    if k == "new":
        state.objects[event["id"]] = {"type": event["type"], "fields": copy.deepcopy(event["fields"])}
    elif k == "set":
        state.objects[event["id"]]["fields"][event["field"]] = copy.deepcopy(event["value"])
    elif k == "call": state.last_call = copy.deepcopy(event)
    elif k == "return": state.last_call = None
    elif k == "result": state.result = copy.deepcopy(event["value"])
    state.event = event


def replay(events: list[dict], count: int | None = None) -> ReplayState:
    # Pilot deliberately uses O(n) replay; keeps backward navigation simple.
    state = ReplayState()
    for e in events[:len(events) if count is None else max(0, min(count, len(events)))]:
        step(state, e)
    return state


def assess(events: list[dict]) -> list[Finding]:
    """Never uses variant to decide PASS/FAIL; it is a display label only."""
    validate(events)
    findings, state, checkpoints, calls, cycles = [], ReplayState(), {}, [], {}
    def add(category, ok, title, detail, evidence):
        findings.append(Finding(category, "PASS" if ok else "FAIL", title, detail, evidence))
    for e in events:
        step(state, e)
        k = e["kind"]
        if k == "call":
            calls.append(e)
            for cy in cycles.values():
                if cy["end"] is None and e["from"] == "subject" and e["method"] == "update": cy["calls"].append(e)
        elif k == "checkpoint":
            ok = state.objects == e["observed"]
            add("integrity", ok, f"状態照合: {e['name']}",
                "再構成状態とJavaの直接観測が一致。" if ok else "記録からの再構成とJava観測が不一致。計測漏れも確認する。", [e["seq"]])
            checkpoints[e["name"]] = (copy.deepcopy(state.objects), e["seq"])
        elif k == "cycle_begin":
            if e["cycle"] in cycles: raise TraceError("通知サイクルが重複しています。")
            cycles[e["cycle"]] = {"begin": e, "calls": [], "end": None}
        elif k == "cycle_end":
            if e["cycle"] not in cycles or cycles[e["cycle"]]["end"] is not None:
                raise TraceError("通知サイクルの開始・終了が対応しません。")
            cycles[e["cycle"]]["end"] = e
    complete = events[-1]["kind"] == "end" and events[-1].get("complete") is True
    lesson, x = events[0]["lesson"], events[0]["input"]
    required = {"references": {"alias", "write"}, "strategy": {"regular", "first_quote", "switch", "second_quote"},
                "state": {"ready", "unlock", "pass"}, "observer": {"subscribed", "notified", "removed", "notified_again"}}[lesson]
    has_cycles = lesson != "observer" or set(cycles) == {"first", "second"} and all(c["end"] for c in cycles.values())
    if not complete or state.result is None or not required.issubset(checkpoints) or not has_cycles:
        findings.append(Finding("contract", "UNKNOWN", "教材契約は未判定", "完了記録・必須観測点・通知境界のいずれかが不足。", []))
        return findings
    def cp(name): return checkpoints[name][0]
    def field_at(name, obj, f): return cp(name).get(obj, {}).get("fields", {}).get(f)
    if lesson == "references":
        refs = cp("alias").get("refs", {}).get("fields", {})
        add("contract", refs.get("a") == refs.get("b") and isinstance(refs.get("a"), dict),
            "同一性", "この課題ではaとbが同じBoxを参照する。", [checkpoints["alias"][1]])
        expected = {"a": x, "b": x, "same": True}
    elif lesson == "strategy":
        targets = [e["to"] for e in calls if e["from"] == "context" and e["method"] == "quote"]
        add("contract", targets == ["regular", "discount"], "委譲先の交換",
            f"期待: regular → discount / 実際: {targets}", [e["seq"] for e in calls])
        add("contract", field_at("switch", "context", "price") == {"ref": "discount"},
            "Contextの参照", "交換後のpriceはDiscountを参照する。", [checkpoints["switch"][1]])
        expected = {"total": x * 8 // 10, "selected": "discount"}
    elif lesson == "state":
        add("contract", field_at("unlock", "gate", "state") == {"ref": "open"},
            "解錠後の状態", "解錠要求の後はOpenを保持する。", [checkpoints["unlock"][1]])
        expected = {"passed": 1, "state": "locked"}
    else:
        for name, cy in cycles.items():
            members = [v["ref"] for v in cy["begin"]["members"]]
            delivered = [e["to"] for e in cy["calls"]]
            add("contract", Counter(members) == Counter(delivered), f"通知 {name}",
                f"登録先: {members} / 実際の呼び出し先: {delivered}",
                [cy["begin"]["seq"], *[c["seq"] for c in cy["calls"]], cy["end"]["seq"]])
        expected = {"a_updates": 2, "b_updates": 1, "a_value": x+1, "b_value": x}
    results = [e for e in events if e["kind"] == "result"]
    add("contract", state.result == expected, "最終結果", f"期待: {expected} / 実際: {state.result}", [results[-1]["seq"]])
    return findings


def overall(findings: list[Finding], category="contract") -> str:
    statuses = [f.status for f in findings if f.category == category]
    if "FAIL" in statuses: return "FAIL"
    if not statuses or "UNKNOWN" in statuses: return "UNKNOWN"
    return "PASS"


def save_trace(events: list[dict], path: Path):
    validate(events)
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")


def summary(events: list[dict]):
    f = assess(events)
    return {"contract": overall(f), "integrity": overall(f, "integrity"), "events": len(events),
            "findings": [x.to_dict() for x in f]}
