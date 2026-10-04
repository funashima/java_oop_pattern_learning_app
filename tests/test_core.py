import copy
import tempfile
import unittest
from pathlib import Path
from pattern_lab.core import ROOT, LESSONS, TraceError, load_trace, parse_trace, validate, assess, overall, replay, save_trace

class CoreTests(unittest.TestCase):
    def trace(self, lesson='strategy', variant='normal'):
        return load_trace(ROOT/'traces'/f'{lesson}_{variant}.jsonl')
    def test_all_bundled_contracts_and_independent_observations(self):
        for lesson in LESSONS:
            for variant in ('normal','broken'):
                with self.subTest(lesson=lesson,variant=variant):
                    f=assess(self.trace(lesson,variant))
                    self.assertEqual(overall(f), 'PASS' if variant=='normal' else 'FAIL')
                    self.assertEqual(overall(f,'integrity'),'PASS')
    def test_variant_label_is_not_oracle(self):
        for lesson in LESSONS:
            ev=self.trace(lesson,'broken');ev[0]['variant']='normal'
            self.assertEqual(overall(assess(ev)),'FAIL')
    def test_truncated_trace_unknown(self):
        for lesson in LESSONS:
            self.assertEqual(overall(assess(self.trace(lesson)[:-2])),'UNKNOWN')
    def test_missing_mandatory_observation_unknown(self):
        ev=self.trace();ev=[e for e in ev if not (e['kind']=='checkpoint' and e['name']=='switch')]
        for i,e in enumerate(ev,1):e['seq']=i
        self.assertEqual(overall(assess(ev)),'UNKNOWN')
    def test_missing_set_detected_by_independent_checkpoint(self):
        ev=self.trace('references')
        ev=[e for e in ev if not (e['kind']=='set' and e['field']=='value')]
        for i,e in enumerate(ev,1):e['seq']=i
        self.assertEqual(overall(assess(ev),'integrity'),'FAIL')
    def test_replay_is_pure_and_backward_deterministic(self):
        for lesson in LESSONS:
            ev=self.trace(lesson); original=copy.deepcopy(ev)
            forward=[replay(ev,n).digest() for n in range(len(ev)+1)]
            backward=[replay(ev,n).digest() for n in reversed(range(len(ev)+1))]
            self.assertEqual(forward,list(reversed(backward)));self.assertEqual(ev,original)
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.jsonl';ev=self.trace('observer');save_trace(ev,p)
            self.assertEqual(ev,load_trace(p))
    def test_evidence_and_source_lines_exist(self):
        lines=(ROOT/'java'/'PatternPilot.java').read_text().splitlines()
        for lesson in LESSONS:
            for variant in ('normal','broken'):
                ev=self.trace(lesson,variant)
                for f in assess(ev):self.assertTrue(all(1<=i<=len(ev) for i in f.evidence))
                for e in ev:self.assertTrue(1<=e['line']<=len(lines))
    def test_sequence_gap_rejected(self):
        ev=self.trace();ev[3]['seq']=99
        with self.assertRaises(TraceError):validate(ev)
    def test_unknown_reference_rejected(self):
        ev=self.trace();next(e for e in ev if e['kind']=='set')['value']={'ref':'absent'}
        with self.assertRaises(TraceError):validate(ev)
    def test_unsupported_schema_rejected(self):
        ev=self.trace();ev[0]['schema']=2
        with self.assertRaises(TraceError):validate(ev)
    def test_malformed_json_rejected(self):
        with self.assertRaises(TraceError):parse_trace('{')
    def test_events_after_end_rejected(self):
        ev=self.trace();ev.append(dict(ev[-1],seq=len(ev)+1))
        with self.assertRaises(TraceError):validate(ev)

if __name__=='__main__':unittest.main()
