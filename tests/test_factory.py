import copy
import unittest
from pattern_lab.core import ROOT, TraceError, assess, load_trace, overall, replay, validate
from pattern_lab.runner import run_java


class FactoryTests(unittest.TestCase):
    def trace(self):
        return load_trace(ROOT / 'traces' / 'abstract_factory_normal.jsonl')

    def finding(self, events, title):
        return next(f.status for f in assess(events) if f.title == title)

    def test_family_and_roundtrip_are_separate(self):
        events = self.trace()
        for event in events:
            if event['kind'] == 'new' and event['id'] == 'hex_decoder':
                event['fields']['family'] = 'decimal'
            if event['kind'] == 'checkpoint' and 'hex_decoder' in event['observed']:
                event['observed']['hex_decoder']['fields']['family'] = 'decimal'
        self.assertEqual(overall(assess(events), 'integrity'), 'PASS')
        self.assertEqual(self.finding(events, '系列整合: hex'), 'FAIL')
        self.assertEqual(self.finding(events, '往復変換: hex'), 'PASS')

    def test_wrong_decode_argument_does_not_hide_behind_correct_state(self):
        events = self.trace()
        next(e for e in events if e['kind'] == 'call' and e['to'] == 'hex_decoder')['arg'] = 'wrong'
        self.assertEqual(overall(assess(events), 'integrity'), 'PASS')
        self.assertEqual(self.finding(events, '操作の合成: hex'), 'FAIL')

    def test_factory_return_must_match_retained_product(self):
        events = self.trace()
        next(e for e in events if e['kind'] == 'return' and e['value'] == {'ref': 'hex_encoder'})['value'] = {'ref': 'decimal_encoder'}
        self.assertEqual(self.finding(events, '製品取得: hex'), 'FAIL')

    def test_missing_creation_pair_fails_despite_intact_checkpoints(self):
        events = self.trace()
        call = next(e for e in events if e['kind'] == 'call' and e['to'] == 'hex_factory' and e['method'] == 'createEncoder')
        ret = next(e for e in events if e['kind'] == 'return' and e.get('value') == {'ref': 'hex_encoder'})
        events = [e for e in events if e is not call and e is not ret]
        for seq, event in enumerate(events, 1): event['seq'] = seq
        self.assertEqual(overall(assess(events), 'integrity'), 'PASS')
        self.assertEqual(self.finding(events, '製品取得: hex'), 'FAIL')

    def test_wrong_return_target_rejected(self):
        events = self.trace()
        next(e for e in events if e['kind'] == 'return')['from'] = 'client'
        with self.assertRaises(TraceError): validate(events)

    def test_unknown_return_reference_rejected(self):
        events = self.trace()
        next(e for e in events if e['kind'] == 'return')['value'] = {'ref': 'absent'}
        with self.assertRaises(TraceError): validate(events)

    def test_missing_payload_rejected(self):
        events = self.trace()
        del next(e for e in events if e['kind'] == 'call')['arg']
        with self.assertRaises(TraceError): validate(events)

    def test_factory_input_bounds(self):
        for value in (-1, 256, True):
            events = self.trace(); events[0]['input'] = value
            with self.assertRaises(TraceError): validate(events)
            with self.assertRaises(TraceError): run_java('abstract_factory', value=value)

    def test_exception_clears_current_call(self):
        events = self.trace()
        call = next(e for e in events if e['kind'] == 'call' and e['to'] == 'hex_decoder')
        events = copy.deepcopy(events[:call['seq']])
        events.append({'seq': len(events)+1, 'kind': 'exception', 'line': 1, 'from': 'hex_decoder', 'error': 'ParseError'})
        validate(events)
        self.assertIsNone(replay(events).last_call)
        self.assertEqual(overall(assess(events)), 'UNKNOWN')

    def test_duplicate_checkpoint_is_not_a_second_operation(self):
        events = self.trace()
        checkpoint = next(e for e in events if e['kind'] == 'checkpoint')
        events.insert(checkpoint['seq'], copy.deepcopy(checkpoint))
        for seq, event in enumerate(events, 1): event['seq'] = seq
        self.assertEqual(self.finding(events, '操作境界の順序'), 'FAIL')

    def test_schema_one_keeps_integer_payload_restriction(self):
        events = load_trace(ROOT / 'traces' / 'strategy_normal.jsonl')
        next(e for e in events if e['kind'] == 'call')['arg'] = '100'
        with self.assertRaises(TraceError): validate(events)


if __name__ == '__main__': unittest.main()
