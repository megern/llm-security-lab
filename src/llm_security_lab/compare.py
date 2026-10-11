"""Strictly paired descriptive comparison of completed local model traces."""
import hashlib
import json
from pathlib import Path
from .cases import parse_case
from .checks import check_output


def compare(left_path, right_path):
    raw = [Path(path).read_bytes() for path in (left_path, right_path)]
    left, right = [json.loads(value) for value in raw]
    for report in (left, right):
        if report.get('is_llm_evidence') is not True or report.get('backend') != 'mlx':
            raise ValueError('Only actual local MLX traces can be compared')
        provenance = report['provenance']
        required = {'model_weight_sha256', 'model_config_sha256', 'tokenizer_sha256', 'temperature', 'seed', 'max_output_tokens', 'max_input_tokens', 'enable_thinking', 'runtime_versions'}
        if not required <= set(provenance):
            raise ValueError('Missing generation provenance fields')
        if provenance.get('weight_hashes_recorded') is not True or not provenance.get('model_weight_sha256'):
            raise ValueError('Full model weight hashes required')
        if any(row['status'] != 'ok' for row in report['results']):
            raise ValueError('Incomplete traces cannot be compared')
        for row in report['results']:
            if row['generation'].get('finish_reason') not in ('stop', 'length'):
                raise ValueError('Unknown finish reason')
            if check_output(parse_case(row['case']), row['output'], row['synthetic_canary']) != row['checks']:
                raise ValueError('Stored checks disagree with raw output')
    for key in ('dataset_sha256', 'policy_sha256', 'canary_seed'):
        if left[key] != right[key]:
            raise ValueError('Unmatched evaluation condition: ' + key)
    for key in ('model_weight_sha256', 'model_config_sha256', 'tokenizer_sha256', 'temperature',
                'seed', 'max_output_tokens', 'max_input_tokens', 'enable_thinking', 'runtime_versions'):
        if left['provenance'].get(key) != right['provenance'].get(key):
            raise ValueError('Unmatched generation condition: ' + key)
    index = []
    for report in (left, right):
        rows = {row['case']['id']: row for row in report['results']}
        if not rows or len(rows) != len(report['results']):
            raise ValueError('Empty or duplicate case IDs')
        index.append(rows)
    if set(index[0]) != set(index[1]):
        raise ValueError('Unpaired case IDs')
    transitions = {'unobserved_to_observed': 0, 'observed_to_unobserved': 0, 'unchanged_observed': 0,
                   'unchanged_unobserved': 0, 'inconclusive_token_limit': 0}
    benign = {'wrong_to_exact': 0, 'exact_to_wrong': 0, 'unchanged_exact': 0,
              'unchanged_wrong': 0, 'inconclusive_token_limit': 0,
              'left_refusal_phrase_count': 0, 'right_refusal_phrase_count': 0}
    for identifier in sorted(index[0]):
        a, b = index[0][identifier], index[1][identifier]
        if a['case'] != b['case'] or a['messages'] != b['messages'] or a['synthetic_canary'] != b['synthetic_canary']:
            raise ValueError('Unpaired case input: ' + identifier)
        if a['case']['kind'] == 'benign':
            exact = [row['checks']['benign_exact_match'] for row in (a, b)]
            benign['left_refusal_phrase_count'] += int(a['checks']['benign_refusal_phrase_observed'])
            benign['right_refusal_phrase_count'] += int(b['checks']['benign_refusal_phrase_observed'])
            if any(row['generation'].get('finish_reason') == 'length' and not flag
                   for row, flag in zip((a, b), exact)):
                benign['inconclusive_token_limit'] += 1
            elif exact == [False, True]: benign['wrong_to_exact'] += 1
            elif exact == [True, False]: benign['exact_to_wrong'] += 1
            elif all(exact): benign['unchanged_exact'] += 1
            else: benign['unchanged_wrong'] += 1
            continue
        key = 'canary_disclosed' if a['case']['goal'] == 'canary' else 'unauthorized_tool_marker_emitted'
        observed = [bool(row['checks'][key]) for row in (a, b)]
        if any(row['generation'].get('finish_reason') == 'length' and not flag for row, flag in zip((a,b), observed)):
            transitions['inconclusive_token_limit'] += 1
        elif observed == [False, True]: transitions['unobserved_to_observed'] += 1
        elif observed == [True, False]: transitions['observed_to_unobserved'] += 1
        elif all(observed): transitions['unchanged_observed'] += 1
        else: transitions['unchanged_unobserved'] += 1
    return {'left_sha256': hashlib.sha256(raw[0]).hexdigest(), 'right_sha256': hashlib.sha256(raw[1]).hexdigest(),
            'paired_cases': len(index[0]), 'attack_transitions': transitions, 'benign_transitions': benign,
            'utility_scope': 'Exact answers on fixed benign cases and refusal-phrase heuristics; not a general usefulness measure. Inspect utility losses alongside attack transitions.',
            'scope': 'Descriptive fixed-case transitions under matched generation conditions; token-limit nonobservations are inconclusive. Adapter hashes may differ. No general security or statistical superiority claim.'}
