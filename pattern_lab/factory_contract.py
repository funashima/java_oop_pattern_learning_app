"""Contracts for the bounded codec lesson, not a general Abstract Factory detector."""
from .core import Finding


def assess_factory(events, checkpoints):
    findings = []
    x = events[0]["input"]

    def add(ok, title, detail, evidence):
        findings.append(Finding("contract", "PASS" if ok else "FAIL", title, detail, evidence))

    def fields(point, oid):
        return checkpoints[point][0].get(oid, {}).get("fields", {})

    expected_points = [f"{phase}_{point}" for phase in ("decimal", "hex")
                       for point in ("products", "encoded", "decoded")]
    points = [e for e in events if e["kind"] == "checkpoint"]
    add([e["name"] for e in points] == expected_points, "操作境界の順序",
        "各系列の製品取得・符号化・復号をこの順に一度ずつ観測する。", [e["seq"] for e in points])

    lower = 0
    for phase in ("decimal", "hex"):
        factory, encoder, decoder = (phase + suffix for suffix in ("_factory", "_encoder", "_decoder"))
        products, encoded, decoded = (f"{phase}_{point}" for point in ("products", "encoded", "decoded"))
        pseq, eseq, dseq = (checkpoints[point][1] for point in (products, encoded, decoded))
        client = fields(products, "client")
        family = [fields(products, oid).get("family") for oid in (factory, encoder, decoder)]
        add(family == [phase] * 3, f"系列整合: {phase}",
            f"要求系列 {phase} / Factory・Encoder・Decoderの系列 {family}。ラベルは動作の証明ではない。", [pseq])

        calls, pending = [], None
        for event in events[lower:dseq]:
            if event["kind"] == "call":
                pending = event
            elif event["kind"] in ("return", "exception") and pending is not None:
                calls.append((pending, event))
                pending = None
        evidence = [e["seq"] for pair in calls for e in pair]

        def matches(pair, target, method, arg, end_kind, payload):
            call, end = pair
            observed = end.get("value") if end_kind == "return" else end.get("error")
            return (call["from"] == "client" and call["to"] == target and call["method"] == method
                    and type(call["arg"]) is type(arg) and call["arg"] == arg
                    and end["kind"] == end_kind and type(observed) is type(payload) and observed == payload)

        created = (len(calls) == 4
                   and matches(calls[0], factory, "createEncoder", None, "return", {"ref": encoder})
                   and matches(calls[1], factory, "createDecoder", None, "return", {"ref": decoder})
                   and calls[1][1]["seq"] < pseq
                   and client == {"factory": {"ref": factory}, "encoder": {"ref": encoder}, "decoder": {"ref": decoder}})
        add(created, f"製品取得: {phase}",
            "指定Factoryの戻り参照と、Clientの保持参照が対応する。newイベントだけから割当て時刻は推論しない。",
            evidence + [pseq])
        encoded_fields = fields(encoded, "codec_result")
        decoded_fields = fields(decoded, "codec_result")
        wire, value, error = (decoded_fields.get(k) for k in ("wire", "decoded", "error"))
        end_kind, payload = ("return", value) if error is None else ("exception", error)
        composed = (len(calls) == 4 and isinstance(wire, str)
                    and encoded_fields == {"wire": wire, "decoded": None, "error": None}
                    and (error is None and type(value) is int or error == "ParseError" and value is None)
                    and matches(calls[2], encoder, "encode", x, "return", wire)
                    and matches(calls[3], decoder, "decode", wire, end_kind, payload)
                    and pseq < calls[2][0]["seq"] < calls[2][1]["seq"] < eseq
                    and eseq < calls[3][0]["seq"] < calls[3][1]["seq"] < dseq)
        add(composed, f"操作の合成: {phase}",
            "encodeの戻り文字列をdecodeに渡し、戻り値またはParseErrorを結果欄へ対応付ける。",
            evidence + [eseq, dseq])
        canonical = str(x) if phase == "decimal" else format(x, "x")
        add(wire == canonical, f"正準表現: {phase}",
            f"指定系列の表現は {canonical!r} / 記録 {wire!r}。", [eseq, dseq])
        add(error is None and type(value) is int and value == x, f"往復変換: {phase}",
            f"入力 {x} / 復号値 {value!r} / 例外 {error!r}。この入力での判定であり全入力の証明ではない。", [dseq])
        lower = dseq
    return findings
