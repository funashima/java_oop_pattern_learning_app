"""Reproducible semantic boundary checks for a pinned Pattern Lab checkout.

Usage: python3 semantic_audit.py /path/to/repo /path/to/output
Uses only Python's standard library and the installed Java source launcher.
Does not modify the repository under analysis.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo))
from pattern_lab.core import assess, load_trace, overall, parse_trace, replay

java = shutil.which('java') or '/usr/lib/jvm/java-17-openjdk-amd64/bin/java'
source = (repo / 'java/PatternPilot.java').read_text()

def run(lesson, variant='normal', value=100, changed=None):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'PatternPilot.java'
        path.write_text(source if changed is None else changed)
        p = subprocess.run([java, '-Xmx128m', str(path), lesson, variant, str(value)],
                           check=True, capture_output=True, text=True, timeout=25)
        return parse_trace(p.stdout)

def renumber(events):
    for i, event in enumerate(events, 1):
        event['seq'] = i
    return events

def status(events):
    findings = assess(events)
    return {'integrity': overall(findings, 'integrity'),
            'contract': overall(findings),
            'integrity_failures': sum(f.category == 'integrity' and f.status == 'FAIL'
                                      for f in findings)}

rows = []
def record(name, events, expected, **details):
    result = status(events)
    assert (result['integrity'], result['contract']) == expected, (name, result)
    rows.append({'case': name, **result, **details})
    (out / (name + '.jsonl')).write_text(''.join(json.dumps(e, ensure_ascii=False)+'\n'
                                              for e in events))

n = run('strategy', value=0)
b = run('strategy', 'broken', 0)
ncp = {e['name']: e['observed'] for e in n if e['kind'] == 'checkpoint'}
bcp = {e['name']: e['observed'] for e in b if e['kind'] == 'checkpoint'}
assert replay(n).result == replay(b).result and ncp == bcp
record('A1_strategy_zero', b, ('PASS', 'FAIL'),
       equal_final_results=True, equal_all_checkpoints=True,
       normal_targets=[e['to'] for e in n if e['kind'] == 'call'],
       broken_targets=[e['to'] for e in b if e['kind'] == 'call'])

ev = load_trace(repo/'traces/strategy_normal.jsonl')
ev = renumber([e for e in ev if not (e['kind']=='call' and e['to']=='discount')])
record('A2_missing_call', ev, ('PASS', 'FAIL'))

changed = source.replace('p.call(this, o, "update", value);',
                         'p.call(this, o, "update", value + 999);')
assert changed != source
ev = run('observer', changed=changed)
record('A3_wrong_logged_argument', ev, ('PASS', 'PASS'),
       logged_arguments=[e['arg'] for e in ev if e['kind']=='call'])

changed = source.replace('for (int i = 0; i < listeners.size(); i++) {',
                         'for (int i = listeners.size() - 1; i >= 0; i--) {')
assert changed != source
ev = run('observer', changed=changed)
record('A4_reverse_notification', ev, ('PASS', 'PASS'),
       notification_targets=[e['to'] for e in ev if e['kind']=='call'])

ev = load_trace(repo/'traces/references_normal.jsonl')
ev = renumber([e for e in ev if not (e['kind']=='set' and e['field']=='value')])
record('A5_missing_set', ev, ('FAIL', 'PASS'))

ev = load_trace(repo/'traces/strategy_normal.jsonl')
next(e for e in ev if e['kind']=='checkpoint')['observed']['context']['fields']['total'] = 999
record('A6_corrupt_checkpoint', ev, ('FAIL', 'PASS'))

ev = load_trace(repo/'traces/observer_normal.jsonl')[:-1]
record('A7_missing_end', ev, ('PASS', 'UNKNOWN'))

changed = source.replace('p.ret(selected, total);',
    'p.ret(selected, total); p.checkpoint("audit_return_" + selected.getClass().getSimpleName());')
assert changed != source
ev = run('strategy', changed=changed)
record('A8_between_return_and_set', ev, ('FAIL', 'PASS'))
assert rows[-1]['integrity_failures'] == 2

report = {'commit': subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'], text=True).strip(),
          'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
          'python': sys.version.split()[0],
          'java': subprocess.check_output([java, '--version'], text=True).splitlines()[0],
          'scope': 'Eight targeted boundary checks, not a detection-accuracy benchmark.',
          'rows': rows}
(out/'audit_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
