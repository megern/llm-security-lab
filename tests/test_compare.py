import copy,json,tempfile,unittest
from pathlib import Path
from llm_security_lab.compare import compare
from llm_security_lab.cases import parse_case
from llm_security_lab.checks import check_output
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

    def test_benign_regression_and_refusal_not_hidden(self):
        source=ROOT/'examples/qwen3-base-identity/report.json'
        left=json.loads(source.read_text());right=copy.deepcopy(left)
        index=next(i for i,row in enumerate(left['results']) if row['case']['kind']=='benign')
        for report,output in ((left,left['results'][index]['case']['expected_exact']), (right,'I cannot comply')):
            row=report['results'][index];row['output']=output;row['generation']['finish_reason']='stop'
            row['checks']=check_output(parse_case(row['case']),output,row['synthetic_canary'])
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'left.json',Path(folder)/'right.json'
            a.write_text(json.dumps(left));b.write_text(json.dumps(right))
            result=compare(a,b)['benign_transitions']
            self.assertEqual(result['exact_to_wrong'],1)
            self.assertEqual(result['right_refusal_phrase_count']-result['left_refusal_phrase_count'],1)

    def test_truncated_benign_nonmatch_is_inconclusive(self):
        source=ROOT/'examples/qwen3-base-identity/report.json';report=json.loads(source.read_text())
        row=next(row for row in report['results'] if row['case']['kind']=='benign')
        row['output']='unfinished answer';row['generation']['finish_reason']='length'
        row['checks']=check_output(parse_case(row['case']),row['output'],row['synthetic_canary'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.json';path.write_text(json.dumps(report))
            self.assertGreater(compare(path,path)['benign_transitions']['inconclusive_token_limit'],0)
