"""Eight frozen healthy controls: exact accounting and no unexpected codes."""
import json
from pathlib import Path
import tempfile
import unittest
from support import ROOT, apply_mutation, evaluate_validation_input, tree_hash
from test_corruptions import state_errors,record_results


class FrozenControls(unittest.TestCase):
    def test_eight_healthy_controls(self):
        manifest=json.loads((ROOT/'fixtures/controls/manifest.json').read_text())
        self.assertEqual([c['id'] for c in manifest['controls']],[f'H{i:02}' for i in range(1,9)])
        records=[]
        for case in manifest['controls']:
            parent=ROOT/case['parent'];self.assertEqual(tree_hash(parent),case['parent_sha256'])
            with tempfile.TemporaryDirectory() as tmp:
                result=evaluate_validation_input(apply_mutation(parent,case['id'],Path(tmp)/'input'))
                errors=state_errors(result,case)
                unexpected=sorted(set(result['codes'])-set(case['allowed_codes']))
                if unexpected:errors.append('unexpected findings: '+','.join(unexpected))
                records.append(dict(id=case['id'],healthy=not errors,codes=result['codes'],errors=errors))
            self.assertEqual(tree_hash(parent),case['parent_sha256'])
        summary=dict(total=8,healthy=sum(r['healthy'] for r in records),unexpected_controls=sum(not r['healthy'] for r in records),controls=records)
        record_results('controls',summary)
        self.assertEqual(summary['unexpected_controls'],0,json.dumps(summary,indent=2))
