"""Frozen twenty-case denominator; exact intended diagnostics and states only."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from support import ROOT, apply_mutation, evaluate_validation_input, tree_hash


def state_errors(result, case):
    errors=[]
    if result['stage'] != case['required_stage']:
        errors.append(f"stage {result['stage']} != {case['required_stage']}")
    if 'expected_code' in case and case['expected_code'] not in result['codes']:
        errors.append('missing intended finding '+case['expected_code'])
    for path,expected in case['expected_states'].items():
        actual=result['evaluation']
        try:
            for key in path.split('/'):
                actual=actual[int(key)] if isinstance(actual,list) else actual[key]
        except (KeyError,TypeError,IndexError): actual='<absent>'
        if actual!=expected: errors.append(f'{path}: {actual!r} != {expected!r}')
    return errors


def record_results(name, value):
    directory=os.environ.get('PILOTPACK_VALIDATION_RESULTS')
    if directory:
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        path=target/(name+'.json')
        if path.exists(): raise FileExistsError('Never overwrite protected results: '+str(path))
        path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
    print(name+': '+json.dumps(value,sort_keys=True))


class FrozenCorruptions(unittest.TestCase):
    def test_frozen_twenty_case_acceptance(self):
        manifest=json.loads((ROOT/'fixtures/corruptions/manifest.json').read_text())
        protocol=json.loads((ROOT/'protocol.json').read_text())
        self.assertEqual(protocol['corruption_manifest_sha256'],hashlib.sha256((ROOT/'fixtures/corruptions/manifest.json').read_bytes()).hexdigest())
        self.assertEqual([c['id'] for c in manifest['cases']],[f'C{i:02}' for i in range(1,21)])
        records=[]
        for case in manifest['cases']:
            parent=ROOT/case['parent']; self.assertEqual(tree_hash(parent),case['parent_sha256'])
            with tempfile.TemporaryDirectory() as tmp:
                result=evaluate_validation_input(apply_mutation(parent,case['id'],Path(tmp)/'input'))
                errors=state_errors(result,case)
                records.append(dict(id=case['id'],critical=case['critical'],detected=not errors,
                                    stage=result['stage'],codes=result['codes'],errors=errors))
            self.assertEqual(tree_hash(parent),case['parent_sha256'])
        detected=sum(r['detected'] for r in records)
        critical=sum(r['detected'] and r['critical'] for r in records)
        summary=dict(detected=detected,total=20,critical_detected=critical,critical_total=12,cases=records)
        record_results('corruptions',summary)
        self.assertEqual(critical,12,json.dumps(summary,indent=2))
        self.assertGreaterEqual(detected,18,json.dumps(summary,indent=2))
