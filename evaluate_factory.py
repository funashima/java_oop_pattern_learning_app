"""Exhaust the integrated codec lesson's 256 inputs in each variant; JDK 17+ required."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from pattern_lab.core import ROOT, assess, overall, parse_trace
from pattern_lab.runner import SOURCE, source_hash

HARNESS = '''
public class FactorySweep {
    public static void main(String[] args) {
        for (String variant : new String[]{"normal", "broken"}) {
            for (int x = 0; x <= 255; x++) {
                PatternPilot.p.ids.clear(); PatternPilot.p.objects.clear(); PatternPilot.p.seq = 0;
                PatternPilot.main(new String[]{"abstract_factory", variant, Integer.toString(x)});
                System.out.println();
            }
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'results' / 'factory_sweep.json')
    args = parser.parse_args()
    if not shutil.which('java'):
        raise SystemExit('JDK 17以降のjavaが必要です。')
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        (target / 'PatternPilot.java').write_bytes(SOURCE.read_bytes())
        (target / 'FactorySweep.java').write_text(HARNESS, encoding='utf-8')
        compiler = [shutil.which('javac')] if shutil.which('javac') else ['java', 'CompileSources.java']
        if not shutil.which('javac'):
            (target / 'CompileSources.java').write_text(
                'class CompileSources { public static void main(String[] args) { '
                'System.exit(javax.tools.ToolProvider.getSystemJavaCompiler().run(null, null, null, args)); } }',
                encoding='utf-8')
        subprocess.run(compiler + ['-encoding', 'UTF-8', 'PatternPilot.java', 'FactorySweep.java'],
                       cwd=target, check=True, capture_output=True, timeout=30)
        process = subprocess.run(['java', '-Xmx128m', '-Dfile.encoding=UTF-8', '-cp', str(target), 'FactorySweep'],
                                 cwd=target, check=True, capture_output=True, text=True, encoding='utf-8', timeout=60)
    rows, counts, integrity_count = [], collections.Counter(), 0
    for text in process.stdout.strip().split('\n\n'):
        events = parse_trace(text)
        findings = assess(events)
        result = next(e['value'] for e in events if e['kind'] == 'result')
        variant, x = events[0]['variant'], events[0]['input']
        outcome = ('parse_error' if result['hex_error'] else
                   'equal' if result['hex_value'] == x else 'different')
        counts[variant + '_' + outcome] += 1
        integrity_count += sum(f.category == 'integrity' for f in findings)
        rows.append({'variant': variant, 'input': x, 'contract': overall(findings),
                     'integrity': overall(findings, 'integrity'), 'hex_outcome': outcome,
                     'hex_value': result['hex_value'], 'hex_error': result['hex_error']})
        # A truthful log of a domain failure must still preserve operation composition.
        expected = 'PASS' if variant == 'normal' else 'FAIL'
        assert overall(findings) == expected and overall(findings, 'integrity') == 'PASS', rows[-1]
        assert all(f.status == 'PASS' for f in findings if f.title.startswith(('操作の合成:', '製品取得:', '正準表現:')))
    assert len(rows) == 512 and integrity_count == 3072
    assert counts == {'normal_equal': 256, 'broken_equal': 10, 'broken_different': 90, 'broken_parse_error': 156}, counts
    report = {'python': platform.python_version(), 'java': events[0]['java'], 'source_sha256': source_hash(),
              'harness_sha256': hashlib.sha256(HARNESS.encode()).hexdigest(),
              'scenario_count': len(rows), 'integrity_checks': integrity_count, 'counts': dict(counts), 'rows': rows,
              'scope': '同一Java教材の全有限入力。Pythonは再生と契約判定を行う。独立Python codec実装との比較ではない。'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
