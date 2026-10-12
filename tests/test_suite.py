import unittest
from unittest.mock import patch
from llm_security_lab.suite import review_suite
class SuiteTests(unittest.TestCase):
    def test_inconclusive_and_benign_regressions_never_pass(self):
        pair={'attack_transitions':{'unobserved_to_observed':0,'inconclusive_token_limit':1},'benign_transitions':{'exact_to_wrong':0,'inconclusive_token_limit':0}}
        with patch('llm_security_lab.suite.compare',return_value=pair):self.assertFalse(review_suite('a',['b'])['all_candidates_passed'])
        pair['attack_transitions']['inconclusive_token_limit']=0;pair['benign_transitions']['exact_to_wrong']=1
        with patch('llm_security_lab.suite.compare',return_value=pair):self.assertFalse(review_suite('a',['b'])['all_candidates_passed'])
    def test_rejected_candidate_is_retained(self):
        with patch('llm_security_lab.suite.compare',side_effect=ValueError('fixture refused')):
            report=review_suite('a',['b']);self.assertEqual(report['results'][0]['status'],'rejected')
