"""Bound, blinded review and descriptive experimental reports.

This module performs no I/O on import. It never promotes exploratory results
into a formal experiment or uses criteria from one matter as independent
statistical observations. Legacy unbound artifacts are rejected, not migrated.
"""
import argparse
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import subprocess
import sys

from run_integrity import (IntegrityError, hash_file, object_hash, sha256_bytes,
                           safe_path, load_manifest, validate_answers, load_blind_manifest)

PROMPT_VERSION = 'bound-review-v1'
PROMPT = """You are grading one criterion of a legal-drafting rubric. Use only the supplied
answer. Judge whether this exact criterion is met. Do not reward length or
fluency. If the answer is silent on the criterion, return FAIL.

CRITERION
{criterion}

SPECIFIC ERROR TO CHECK
{against}

ANSWER
<<<
{output}
>>>

Return exactly one JSON object:
{{"verdict":"PASS" or "FAIL","reason":"One sentence identifying the decisive passage."}}
"""
PROMPT_HASH = sha256_bytes(PROMPT.encode('utf-8'))
STATES = ('PASS', 'FAIL', 'SPLIT', 'UNPARSEABLE', 'ERROR', 'MISSING')


def _fail(message):
    raise IntegrityError(message)


def _checked_shape(operation):
    @wraps(operation)
    def checked(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except (KeyError, TypeError, AttributeError) as exc:
            raise IntegrityError('Invalid bound artifact shape; the result cannot be used.') from exc
    return checked


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique,
                          parse_constant=lambda value: _fail('Nonfinite JSON constant: ' + value))
    except (OSError, UnicodeError, ValueError) as exc:
        raise IntegrityError('Cannot read a valid bound artifact: ' + str(path)) from exc


def _seal(record, field):
    return {**record, field: object_hash(record)}


def _unseal(record, field, schema):
    if not isinstance(record, dict) or record.get('schema_version') != schema:
        _fail('Unsupported or legacy artifact schema; create a new bound run.')
    if record.get(field) != object_hash({k: v for k, v in record.items() if k != field}):
        _fail('Artifact content hash mismatch: ' + field)


def _write_new(path, record):
    # Do not replace old results. A different configuration needs a new run.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def _tasks(run_dir, manifest):
    document = _read(safe_path(Path(run_dir), manifest['tasks_file']))
    if not isinstance(document, dict) or not isinstance(document.get('tasks'), list):
        _fail('Task snapshot has invalid shape.')
    tasks, criteria = {}, set()
    for task in document['tasks']:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not task['id']:
            _fail('Task identity is missing.')
        if task['id'] in tasks or not isinstance(task.get('rubric'), list) or not task['rubric']:
            _fail('Duplicate task or invalid rubric.')
        for criterion in task['rubric']:
            if (not isinstance(criterion, dict) or not isinstance(criterion.get('id'), str)
                    or not criterion['id'] or criterion['id'] in criteria):
                _fail('Missing or duplicate criterion identity.')
            if not all(isinstance(criterion.get(k), str) and criterion[k].strip()
                       for k in ('criterion', 'discriminates_against')):
                _fail('Criterion text/discriminator is missing.')
            criteria.add(criterion['id'])
        tasks[task['id']] = task
    return document, tasks


def _judge_ids(judges, generator=None):
    if not isinstance(judges, list) or len(judges) not in (1, 2):
        _fail('Declare one exploratory judge or two independent judges at execution time.')
    result = []
    for judge in judges:
        if not isinstance(judge, dict):
            _fail('Invalid judge declaration.')
        record = {k: judge.get(k) for k in ('slot', 'id', 'family')}
        if any(not isinstance(v, str) or not v.strip() or v.upper() in ('UNKNOWN', 'UNRECORDED')
               for v in record.values()):
            _fail('Actual judge ID and family must be declared before execution.')
        result.append(record)
    for key in ('slot', 'id', 'family'):
        if len({r[key].casefold() for r in result}) != len(result):
            _fail('Judge declarations must have distinct slots, IDs and families.')
    if generator is not None and not isinstance(generator, dict):
        _fail('Invalid generator declaration.')
    if generator and generator.get('family'):
        if any(j['family'].casefold() == str(generator['family']).casefold() for j in result):
            _fail('A judge may not share the declared generator family.')
    return result


def combine(*judgments):
    values = [j.get('verdict') for j in judgments]
    if not values or any(v not in ('PASS', 'FAIL', 'UNPARSEABLE', 'ERROR') for v in values):
        return 'UNPARSEABLE'
    if 'ERROR' in values:
        return 'ERROR'
    if 'UNPARSEABLE' in values:
        return 'UNPARSEABLE'
    return values[0] if len(set(values)) == 1 else 'SPLIT'


def _parse_reply(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_unique)
        if (not isinstance(value, dict) or value.get('verdict') not in ('PASS', 'FAIL')
                or not isinstance(value.get('reason'), str) or not value['reason'].strip()):
            raise ValueError('Invalid verdict shape')
        return {'verdict': value['verdict'], 'reason': value['reason']}
    except (ValueError, TypeError):
        return {'verdict': 'UNPARSEABLE', 'reason': 'Reply did not match the required verdict schema.'}


def _execute(prompt, judge):
    command = judge.get('command')
    if not isinstance(command, str) or not command.strip():
        _fail('A judge command is required for execution.')
    try:
        result = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                shell=True, encoding='utf-8', timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return {'verdict': 'ERROR', 'reason': 'Judge process failed or exceeded its time limit.'}
    if result.returncode:
        return {'verdict': 'ERROR', 'reason': 'Judge process returned an unsuccessful exit status.'}
    return _parse_reply(result.stdout)


def _judging_document(blind, judges):
    return _seal({'schema_version': 'doctrine-judging-v1',
        'blind_manifest_sha256': blind['blind_manifest_sha256'], 'tasks_sha256': blind['tasks_sha256'],
        'generator': blind.get('model'), 'judge_prompt_version': PROMPT_VERSION,
        'judge_prompt_sha256': PROMPT_HASH, 'judge_identity_basis': 'operator-declared', 'judges': judges}, 'judging_sha256')


def _load_judging(run_dir, blind, required=False):
    path = safe_path(Path(run_dir), 'judging_manifest.json')
    if not path.is_file():
        if required:
            _fail('Missing judging manifest; an unbound verdict cannot be used.')
        return None
    record = _read(path)
    _unseal(record, 'judging_sha256', 'doctrine-judging-v1')
    judges = _judge_ids(record.get('judges'), blind.get('model'))
    if record != _judging_document(blind, judges):
        _fail('Judging configuration, prompt or blind snapshot changed; refuse stale results.')
    return record


def _binding(blind, entry, judging):
    return {'blind_manifest_sha256': blind['blind_manifest_sha256'],
        'judging_sha256': judging['judging_sha256'], 'judge_prompt_sha256': PROMPT_HASH,
        **{k: entry[k] for k in ('label', 'task_id', 'rubric_sha256', 'blinded_sha256', 'answer_sha256')}}


def _verdict(record, blind, entry, judging, task):
    _unseal(record, 'verdict_sha256', 'doctrine-verdict-v1')
    if any(record.get(k) != value for k, value in _binding(blind, entry, judging).items()):
        _fail('Verdict identity/hash mismatch for ' + entry['label'])
    if record.get('judges') != judging['judges']:
        _fail('Verdict judge model declarations do not match execution configuration.')
    rows = record.get('verdicts')
    if not isinstance(rows, list):
        _fail('Verdict criterion records are missing.')
    expected = {c['id']: c for c in task['rubric']}
    actual = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('criterion') not in expected or row['criterion'] in actual:
            _fail('Unknown or duplicate verdict criterion.')
        criterion = expected[row['criterion']]
        if row.get('criterion_sha256') != object_hash(criterion):
            _fail('Verdict criterion changed after judging.')
        judgments = row.get('judgments')
        if not isinstance(judgments, list) or len(judgments) != len(judging['judges']):
            _fail('Missing individual judge result.')
        for value, judge in zip(judgments, judging['judges']):
            if not isinstance(value, dict) or any(value.get(k) != v for k, v in judge.items()):
                _fail('Individual judge identity mismatch.')
            if value.get('verdict') not in ('PASS', 'FAIL', 'UNPARSEABLE', 'ERROR') or not isinstance(value.get('reason'), str):
                _fail('Invalid individual verdict.')
        if row.get('verdict') != combine(*judgments):
            _fail('Combined verdict contradicts individual judgments.')
        actual[row['criterion']] = row['verdict']
    if set(actual) != set(expected):
        _fail('Incomplete criterion coverage in a present verdict; it cannot be scored.')
    return actual


@_checked_shape
def judge_run(run_dir, judges=None, complete=None, dry=False):
    run_dir = Path(run_dir)
    # This is deliberately the blind-only loader. Never load manifest or key.
    blind = load_blind_manifest(run_dir)
    _, tasks = _tasks(run_dir, blind)
    if dry:
        return {'dry_run': True, 'outputs': len(blind['entries']),
                'criteria': sum(len(tasks[e['task_id']]['rubric']) for e in blind['entries']),
                'judge_prompt_version': PROMPT_VERSION, 'writes': 0, 'model_calls': 0}
    identities = _judge_ids(judges, blind.get('model'))
    if complete is None and any(not isinstance(j.get('command'), str) or not j['command'].strip() for j in judges):
        _fail('Judge commands must be supplied before any execution artifact is written.')
    if complete is None and len({j['command'] for j in judges}) != len(judges):
        _fail('Different declared judge families cannot execute the identical command.')
    desired = _judging_document(blind, identities)
    stored = _load_judging(run_dir, blind)
    if stored is not None and stored != desired:
        _fail('Judge models changed; create a new run instead of reusing these verdicts.')
    # Validate all existing verdicts before any process call or file write.
    pending, reused = [], 0
    for entry in blind['entries']:
        path = safe_path(run_dir, 'verdicts/' + entry['label'] + '.json')
        if path.exists():
            if stored is None:
                _fail('Existing verdict has no judging manifest.')
            _verdict(_read(path), blind, entry, stored, tasks[entry['task_id']])
            reused += 1
        else:
            pending.append((entry, path))
    allowed = {e['label'] + '.json' for e in blind['entries']}
    if (run_dir / 'verdicts').exists() and set(p.name for p in (run_dir / 'verdicts').glob('*.json')) - allowed:
        _fail('Unexpected old verdict labels are present; refuse cross-run reuse.')
    if stored is None:
        _write_new(safe_path(run_dir, 'judging_manifest.json'), desired)
    for entry, path in pending:
        text = safe_path(run_dir, entry['blinded_file']).read_text(encoding='utf-8')
        body = text.partition('\n')[2]
        rows = []
        for criterion in tasks[entry['task_id']]['rubric']:
            prompt = PROMPT.format(criterion=criterion['criterion'], against=criterion['discriminates_against'], output=body)
            values = []
            for spec, identity in zip(judges, identities):
                if complete is None:
                    value = _execute(prompt, spec)
                else:
                    try:
                        value = _parse_reply(complete(prompt, spec))
                    except Exception:
                        value = {'verdict': 'ERROR', 'reason': 'Judge callback failed; no verdict was obtained.'}
                values.append({**identity, **value})
            rows.append({'criterion': criterion['id'], 'criterion_sha256': object_hash(criterion),
                         'verdict': combine(*values), 'judgments': values})
        record = _seal({'schema_version': 'doctrine-verdict-v1', **_binding(blind, entry, desired),
            'judges': identities, 'completed_utc': datetime.now(timezone.utc).isoformat(), 'verdicts': rows}, 'verdict_sha256')
        _write_new(path, record)
    return {'judged': len(pending), 'reused_after_identity_validation': reused, 'formal_readiness': False}


def _bound_run(run_dir):
    run_dir = Path(run_dir)
    manifest = load_manifest(run_dir, verify_current=False)
    answers = validate_answers(run_dir, manifest, require_complete=True)
    answer_hashes = {item['entry']['entry_id']: item['meta']['answer_sha256'] for item in answers}
    blind = load_blind_manifest(run_dir)
    if blind.get('manifest_sha256') != manifest['manifest_sha256'] or blind.get('tasks_sha256') != manifest['tasks_sha256']:
        _fail('Blind and source manifests belong to different runs.')
    if blind.get('model') != manifest.get('model') or blind.get('readiness') != manifest.get('readiness'):
        _fail('Blind generator/readiness declarations differ from the source run manifest.')
    key = _read(run_dir / 'blind_key.json')
    if (not isinstance(key, dict) or key.get('schema_version') != 'doctrine-blind-key-v1'
            or key.get('manifest_sha256') != manifest['manifest_sha256']
            or key.get('blind_manifest_sha256') != blind['blind_manifest_sha256']
            or not isinstance(key.get('entries'), dict)):
        _fail('Missing, legacy or mismatched blind key.')
    entries, triples = {}, set()
    for entry in manifest['entries']:
        triple = (entry['task_id'], entry['condition'], entry['variant'])
        if entry['entry_id'] in entries or triple in triples:
            _fail('Duplicate task-condition-variant identity.')
        if entry['condition'] not in ('bare', 'conn'):
            _fail('Unknown condition.')
        entries[entry['entry_id']] = entry
        triples.add(triple)
    expected_pairs = {(t, v) for t, _, v in triples}
    if triples != {(t, c, v) for t, v in expected_pairs for c in ('bare', 'conn')}:
        _fail('Every selected task/variant needs exactly one bare and one connector answer.')
    by_label = {entry['label']: entry for entry in blind['entries']}
    if len(by_label) != len(blind['entries']) or set(key['entries']) != set(by_label):
        _fail('Blind labels are duplicated or incomplete.')
    seen = set()
    for label, value in key['entries'].items():
        if not isinstance(value, dict) or value.get('entry_id') not in entries or value['entry_id'] in seen:
            _fail('Blind key contains a duplicate or unknown entry identity.')
        entry, b = entries[value['entry_id']], by_label[label]
        if any(value.get(k) != entry[k] for k in ('task_id', 'condition', 'variant')):
            _fail('Blind key crosses task or variant identities.')
        if value.get('task_id') != b['task_id'] or value.get('answer_sha256') != b['answer_sha256']:
            _fail('Blind key crosses answer identities.')
        if value.get('answer_sha256') != answer_hashes.get(entry['entry_id']) or b['rubric_sha256'] != entry['rubric_sha256']:
            _fail('Blind key answer/rubric does not match the source manifest entry.')
        seen.add(value['entry_id'])
    if seen != set(entries):
        _fail('Blind key omits a selected answer.')
    document, tasks = _tasks(run_dir, manifest)
    judging = _load_judging(run_dir, blind)
    return manifest, answers, blind, key, document, tasks, judging


@_checked_shape
def score_run(run_dir):
    run_dir = Path(run_dir)
    manifest, answers, blind, key, document, tasks, judging = _bound_run(run_dir)
    costs = {condition: {'answers': 0, 'duration_s': 0.0, 'answer_chars': 0} for condition in ('bare', 'conn')}
    execution_records = []
    for answer in answers:
        entry, meta = answer['entry'], answer['meta']
        cost = costs[entry['condition']]
        cost['answers'] += 1
        cost['duration_s'] += meta['duration_s']
        cost['answer_chars'] += len(answer['answer'])
        execution_records.append({'entry_id': entry['entry_id'],
            'meta_file': entry['meta_file'], 'meta_sha256': hash_file(safe_path(run_dir, entry['meta_file'])),
            **{k: meta[k] for k in ('model_id', 'model_family', 'started_utc', 'ended_utc', 'duration_s')}})
    allowed = {e['label'] + '.json' for e in blind['entries']}
    if (run_dir / 'verdicts').exists() and set(p.name for p in (run_dir / 'verdicts').glob('*.json')) - allowed:
        _fail('Unexpected stale verdict file; refusing an incomplete label join.')
    counts = {c: {s: 0 for s in STATES} for c in ('bare', 'conn')}
    unresolved = {s: 0 for s in STATES if s not in ('PASS', 'FAIL')}
    results, verdict_hashes, rows = {}, {}, []
    for entry in blind['entries']:
        task = tasks[entry['task_id']]
        path = safe_path(run_dir, 'verdicts/' + entry['label'] + '.json')
        if path.exists():
            if judging is None:
                _fail('Present verdicts require a bound judging manifest.')
            value = _read(path)
            result = _verdict(value, blind, entry, judging, task)
            verdict_hashes[entry['label']] = value['verdict_sha256']
        else:
            result = {c['id']: 'MISSING' for c in task['rubric']}
        meta = key['entries'][entry['label']]
        triple = (meta['task_id'], meta['condition'], meta['variant'])
        results[triple] = result
        for state in result.values():
            counts[meta['condition']][state] += 1
            if state in unresolved:
                unresolved[state] += 1
        rows.append({'label': entry['label'], 'task_id': meta['task_id'], 'condition': meta['condition'],
                     'variant': meta['variant'], 'criteria': result})
    task_results = []
    paired = {k: 0 for k in ('both_pass', 'bare_only', 'conn_only', 'both_fail', 'unresolved')}
    for task_id, variant in sorted({(t, v) for t, _, v in results}):
        task = tasks[task_id]
        conditions = {}
        for condition in ('bare', 'conn'):
            values = results[(task_id, condition, variant)]
            per_counts = {s: sum(v == s for v in values.values()) for s in STATES}
            all_pass = 'UNRESOLVED' if any(v not in ('PASS', 'FAIL') for v in values.values()) else 'PASS' if all(v == 'PASS' for v in values.values()) else 'FAIL'
            conditions[condition] = {'counts': per_counts, 'all_pass': all_pass}
        for criterion in task['rubric']:
            a = results[(task_id, 'bare', variant)][criterion['id']]
            b = results[(task_id, 'conn', variant)][criterion['id']]
            category = 'unresolved' if a not in ('PASS', 'FAIL') or b not in ('PASS', 'FAIL') else (
                'both_pass' if a == b == 'PASS' else 'both_fail' if a == b == 'FAIL' else 'bare_only' if a == 'PASS' else 'conn_only')
            paired[category] += 1
        task_results.append({'task_id': task_id, 'variant': variant, 'conditions': conditions})
    return {'schema_version': 'doctrine-descriptive-report-v1', 'status': 'incomplete' if any(unresolved.values()) else 'complete',
        'integrity_valid': True, 'formal_readiness': False, 'analysis_mode': 'paired-descriptive-only',
        'manifest_sha256': manifest['manifest_sha256'], 'blind_manifest_sha256': blind['blind_manifest_sha256'],
        'judging_sha256': judging['judging_sha256'] if judging else None, 'verdict_set_sha256': object_hash(verdict_hashes),
        'dataset': {'name': document.get('dataset'), 'version': document.get('version'),
                    'tasks_file': manifest['tasks_file'], 'tasks_sha256': manifest['tasks_sha256'], 'experiment': manifest.get('experiment')},
        'models': {'generator': manifest.get('model'), 'judges': judging['judges'] if judging else []},
        'costs_by_condition': costs, 'execution_records': execution_records,
        'recorded_readiness': manifest.get('readiness'), 'counts_by_condition': counts,
        'unresolved_counts': unresolved, 'paired_counts': paired, 'task_results': task_results, 'rows': rows,
        'limitations': ['Counts are descriptive paired observations, not independent criterion samples.',
            'Criteria and as-of variants from the same matter are related; no inferential significance or population claim is made.',
            'SPLIT, parse errors, process errors and missing results remain unresolved and are excluded from binary comparisons.',
            'Independent answer-key review, bound human calibration and the formal reporting protocol have not been established by these scripts.',
            'Model IDs and families are execution-time declarations, not independently authenticated provider attestations.']}


@_checked_shape
def evaluation_card(run_dir):
    report = score_run(run_dir)
    return {'schema_version': 'doctrine-evaluation-card-v1', 'generated_utc': datetime.now(timezone.utc).isoformat(),
            **{k: report[k] for k in ('status', 'formal_readiness', 'analysis_mode', 'manifest_sha256',
                'blind_manifest_sha256', 'judging_sha256', 'verdict_set_sha256', 'dataset', 'models',
                'recorded_readiness', 'costs_by_condition', 'execution_records', 'unresolved_counts', 'limitations')}}


def kappa(judged, human):
    """Compatibility math helper only; it grants no reporting/calibration gate."""
    if not judged or len(judged) != len(human) or any(x not in (0, 1) for x in judged + human):
        raise ValueError('Kappa requires aligned, nonempty binary records.')
    n = len(judged)
    observed = sum(a == b for a, b in zip(judged, human)) / n
    p, q = sum(judged) / n, sum(human) / n
    expected = p * q + (1 - p) * (1 - q)
    return (None if expected == 1 else (observed - expected) / (1 - expected), observed)


@_checked_shape
def calibration_run(run_dir):
    # Calibration remains blind: this path never opens the condition key.
    run_dir = Path(run_dir)
    blind = load_blind_manifest(run_dir)
    _, tasks = _tasks(run_dir, blind)
    judging = _load_judging(run_dir, blind, required=True)
    gold = _read(safe_path(run_dir, 'human_gold.json'))
    if (not isinstance(gold, dict) or gold.get('schema_version') != 'doctrine-human-gold-v1'
            or gold.get('blind_manifest_sha256') != blind['blind_manifest_sha256']
            or gold.get('judging_sha256') != judging['judging_sha256'] or not isinstance(gold.get('entries'), list)):
        _fail('Human labels are legacy or unbound; do not reuse them for calibration.')
    entries = {e['label']: e for e in blind['entries']}
    observed, seen, unresolved, verdict_hashes = [], set(), 0, {}
    for row in gold['entries']:
        if not isinstance(row, dict) or row.get('label') not in entries:
            _fail('Human label refers to an unknown blinded answer.')
        entry = entries[row['label']]
        criterion = next((c for c in tasks[entry['task_id']]['rubric'] if c['id'] == row.get('criterion')), None)
        pair = (row['label'], row.get('criterion'))
        if criterion is None or pair in seen or row.get('human') not in ('PASS', 'FAIL'):
            _fail('Human labels have missing, duplicate or invalid criterion identities.')
        seen.add(pair)
        if row.get('answer_sha256') != entry['answer_sha256'] or row.get('criterion_sha256') != object_hash(criterion):
            _fail('Human gold answer/criterion identity changed.')
        if not all(isinstance(row.get(k), str) and row[k].strip() for k in ('reader', 'reviewed_utc')):
            _fail('Human labels need their original reader and review date declarations.')
        try:
            reviewed = datetime.fromisoformat(row['reviewed_utc'].replace('Z', '+00:00'))
            if reviewed.tzinfo is None or reviewed.utcoffset().total_seconds() != 0:
                raise ValueError('UTC date required')
        except ValueError as exc:
            raise IntegrityError('Human review date must be an actual UTC timestamp.') from exc
        record = _read(safe_path(run_dir, 'verdicts/' + entry['label'] + '.json'))
        result = _verdict(record, blind, entry, judging, tasks[entry['task_id']])[criterion['id']]
        verdict_hashes[entry['label']] = record['verdict_sha256']
        if result not in ('PASS', 'FAIL'):
            unresolved += 1
        else:
            observed.append(result == row['human'])
    return {'schema_version': 'doctrine-descriptive-calibration-v1', 'formal_readiness': False,
        'blind_manifest_sha256': blind['blind_manifest_sha256'], 'judging_sha256': judging['judging_sha256'],
        'verdict_set_sha256': object_hash(verdict_hashes),
        'human_gold_sha256': hash_file(run_dir / 'human_gold.json'), 'binary_pairs': len(observed),
        'unresolved_pairs': unresolved, 'matching_binary_pairs': sum(observed),
        'raw_agreement': sum(observed) / len(observed) if observed else None,
        'limitation': 'Descriptive agreement for supplied bound human labels only; no automatic reporting threshold or adjustment is applied.'}


@_checked_shape
def invariance_run(base_dir, variant_dir):
    base, variant = score_run(base_dir), score_run(variant_dir)
    if base['dataset']['tasks_sha256'] != variant['dataset']['tasks_sha256'] or base['models'] != variant['models']:
        _fail('Invariance rounds must share exactly the task/rubric snapshot and model declarations.')
    def triples(report, expected_variant):
        output = {}
        for row in report['rows']:
            if row['variant'] != expected_variant:
                _fail('Invariance round contains an unexpected or duplicate variant.')
            for criterion, value in row['criteria'].items():
                identity = (row['task_id'], row['condition'], criterion)
                if identity in output:
                    _fail('Duplicate invariance identity.')
                output[identity] = value
        return output
    left, right = triples(base, 'base'), triples(variant, 'inv')
    if not left or set(left) != set(right):
        _fail('Invariance rounds have incomplete or different selected criteria; do not compare their intersection.')
    binary = [key for key in left if left[key] in ('PASS', 'FAIL') and right[key] in ('PASS', 'FAIL')]
    return {'schema_version': 'doctrine-descriptive-invariance-v1', 'formal_readiness': False,
        'base_manifest_sha256': base['manifest_sha256'], 'variant_manifest_sha256': variant['manifest_sha256'],
        'base_bindings': {k: base[k] for k in ('blind_manifest_sha256', 'judging_sha256', 'verdict_set_sha256')},
        'variant_bindings': {k: variant[k] for k in ('blind_manifest_sha256', 'judging_sha256', 'verdict_set_sha256')},
        'matched_binary_pairs': len(binary), 'unresolved_pairs': len(left) - len(binary),
        'pass_to_fail': sum(left[k] == 'PASS' and right[k] == 'FAIL' for k in binary),
        'fail_to_pass': sum(left[k] == 'FAIL' and right[k] == 'PASS' for k in binary),
        'limitation': 'Descriptive changes across bound variants; unresolved results are not flips or failures, and shared criteria are not independent samples.'}


def _cli_result(operation):
    try:
        return operation()
    except (IntegrityError, OSError, ValueError) as exc:
        print(json.dumps({'integrity_valid': False, 'formal_readiness': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


def _default_runs(here):
    here = Path(here).resolve()
    if here.name == 'exp4-cfa':
        value = os.environ.get('EXP4_RUNS_DIR') or os.environ.get('EXP3_RUNS_DIR')
    else:
        value = os.environ.get('EXP3_RUNS_DIR')
    path = Path(value) if value else here / 'runs'
    return (here / path).resolve() if not path.is_absolute() else path.resolve()


def judge_main(here, argv=None):
    parser = argparse.ArgumentParser(description='Judge only verified blind-manifest entries; never reuse unbound verdicts.')
    parser.add_argument('--runs', type=Path, default=_default_runs(here))
    parser.add_argument('--dry', action='store_true', help='verify blind inputs and report planned counts without writes or model calls')
    args = parser.parse_args(argv)
    def operation():
        judges = None
        if not args.dry:
            slots = ('A', 'B') if os.environ.get('JUDGE_CMD_A') and os.environ.get('JUDGE_CMD_B') else ('single',)
            judges = [{'slot': slot, 'id': os.environ.get('JUDGE_ID' if slot == 'single' else 'JUDGE_ID_' + slot),
                'family': os.environ.get('JUDGE_FAMILY' if slot == 'single' else 'JUDGE_FAMILY_' + slot),
                'command': os.environ.get('JUDGE_CMD' if slot == 'single' else 'JUDGE_CMD_' + slot)} for slot in slots]
        print(json.dumps(judge_run(args.runs, judges, dry=args.dry), ensure_ascii=False, indent=2))
        return 0
    return _cli_result(operation)


def report_main(kind, here, argv=None):
    parser = argparse.ArgumentParser(description='Validate artifact identities and produce an exploratory descriptive ' + kind + ' report.')
    parser.add_argument('--runs', type=Path, default=_default_runs(here))
    parser.add_argument('--json', action='store_true', help='JSON is the report format; retained for explicit automation')
    parser.add_argument('--output', type=Path, help='write a NEW report file; existing artifacts are never overwritten')
    if kind == 'invariance':
        parser.add_argument('base_dir', nargs='?', type=Path)
        parser.add_argument('variant_dir', nargs='?', type=Path)
    args = parser.parse_args(argv)
    def operation():
        if kind == 'score': report = score_run(args.runs)
        elif kind == 'evaluation-card': report = evaluation_card(args.runs)
        elif kind == 'calibration': report = calibration_run(args.runs)
        else: report = invariance_run(args.base_dir or args.runs, args.variant_dir or Path(here) / 'runs_inv')
        if args.output:
            _write_new(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if kind == 'score' and report.get('status') == 'incomplete' else 0
    return _cli_result(operation)
