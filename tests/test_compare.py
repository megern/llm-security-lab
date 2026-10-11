import copy,json,tempfile,unittest
from pathlib import Path
from llm_security_lab.compare import compare
ROOT=Path(__file__).resolve().parents[1]
class CompareTests(unittest.TestCase):
    def test_identical_and_truncated_attacks(self):
        path=ROOT/'examples/qwen3-base-identity/report.json'
        report=compare(path,path)
        self.assertEqual(report['paired_cases'],32)
        self.assertGreater(report['attack_transitions']['inconclusive_token_limit'],0)
        self.assertEqual(report['attack_transitions']['observed_to_unobserved'],0)
    def test_changed_generation_or_checks_rejected(self):
        source=ROOT/'examples/qwen3-base-identity/report.json'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'changed.json';original=json.loads(source.read_text())
            for change in ('budget','checks','fixture'):
                data=copy.deepcopy(original)
                if change=='budget':data['provenance']['max_output_tokens']+=1
                elif change=='checks':data['results'][0]['checks']['canary_disclosed']=not data['results'][0]['checks']['canary_disclosed']
                else:data['is_llm_evidence']=False
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):compare(source,path)
