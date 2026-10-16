"""Small, inspectable packet builders; no product imports."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))


def make_packet(root, scenario='same-text-distinct-tasks'):
    target = Path(root) / 'packet'
    shutil.copytree(ROOT / 'fixtures/canonical/schema-small', target)
    return target


def rehash(root):
    manifest = json.loads((root / 'packet.json').read_text())
    manifest['hashes'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'packet.json'}
    manifest['protocol_sha256'] = manifest['hashes']['protocol.json']
    write_json(root / 'packet.json', manifest)


def canonical_records(root):
    """Read complete canonical-only fixture records without product helpers."""
    root = make_packet(root)
    values = {name: tuple(json.loads(line) for line in (root / (name + '.jsonl')).read_text().splitlines())
              for name in ('tasks', 'assignments', 'outcomes', 'attempts')}
    values['sources'] = tuple(json.loads((root / 'sources.json').read_text())['sources'])
    values['manifest'] = json.loads((root / 'packet.json').read_text())
    values['protocol'] = json.loads((root / 'protocol.json').read_text())
    values['root'] = root
    values['diagnostics'] = (dict(code='TEST_LIMITATION', severity='limitation', scope='packet',
                                 source_refs=['src#$'], message='Synthetic control'),)
    return values


def tree_hash(root: Path) -> str:
    """Bind all parent bytes and relative filenames, including packet.json."""
    entries = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(root.rglob('*')) if p.is_file()}
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def _inventory(root):
    inventory = json.loads((root / 'sources.json').read_text())
    for source in inventory['sources']:
        path = root / source['local_path']
        if path.is_file() and not path.is_symlink():
            source.update(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    write_json(root / 'sources.json', inventory)


def _add_source(root, sid, path, value, role='synthetic-control'):
    write_json(root / path, value)
    inventory = json.loads((root / 'sources.json').read_text())
    inventory['sources'].append(dict(inventory['sources'][0], source_id=sid, local_path=path,
                                    role=role, parents=['src']))
    write_json(root / 'sources.json', inventory)


def apply_mutation(parent: Path, mutation_id: str, out: Path) -> Path:
    """Copy first, apply one frozen recipe, rehash semantic inputs before import."""
    import copy
    shutil.copytree(parent, out)
    m = json.loads((out / 'packet.json').read_text())
    p = json.loads((out / 'protocol.json').read_text())
    data = {name: [json.loads(s) for s in (out / (name + '.jsonl')).read_text().splitlines()]
            for name in ('tasks', 'assignments', 'outcomes', 'attempts')}
    tasks, assignments, outcomes, attempts = (data[n] for n in ('tasks','assignments','outcomes','attempts'))
    ident = mutation_id
    if ident == 'C01':
        (out / 'raw/evidence.json').write_bytes(b'{"altered":true}\n')
        return out
    if ident == 'C02': assignments.append(copy.deepcopy(assignments[0]))
    elif ident == 'C03': outcomes.append(dict(outcomes[0], assignment_id='absent'))
    elif ident == 'C04': outcomes.pop(0)
    elif ident == 'C05':
        tasks.append(dict(tasks[0], task_id='replacement', cohort_id='other-gold', gold_ids={'arxiv':['9999.99999']}))
        assignments[3]['task_id'] = 'replacement'
    elif ident in ('C06','C07','C08'):
        key,value = {'C06':('k',1),'C07':('snippet_chars',12),'C08':('mode','pro')}[ident]
        m['actual_settings']['a'][key] = value
        if ident == 'C06': m['actual_settings']['a']['requested_num_results'] = 1
    elif ident == 'C09':
        outcomes[0].update(observation_kind='not_dispatched',terminal_status='runner_failure',selected_attempt_id=None,results=None,reported_hit_rank=None)
        attempts[:] = [x for x in attempts if x['assignment_id'] != 'a:t1']
    elif ident == 'C10':
        miss = dict(outcomes[0]['results'][0], url='https://example.org/unrelated')
        outcomes[1].update(results=[miss],reported_hit_rank=1)
        attempts[1]['results'] = [miss]
    elif ident == 'C11':
        later = dict(attempts[1], attempt_index=2, attempt_id='a-later-hit',results=copy.deepcopy(outcomes[0]['results']))
        attempts.append(later)
        outcomes[1].update(selected_attempt_id='a-later-hit',results=later['results'],reported_hit_rank=1)
    elif ident == 'C12': attempts[0]['cost'] = dict(amount='0',currency='USD',kind='observed',scope='attempt',source_ref=None)
    elif ident in ('C13','C14','H03'):
        data['attempts'] = [x for x in attempts if not (ident == 'C13' or x['assignment_id'].startswith('a:'))]
        for row in outcomes:
            if ident == 'C13' or row['assignment_id'].startswith('a:'):
                row.update(observation_kind='archive_logical',selected_attempt_id=None)
        if ident == 'H03': m['attempt_history']['a'] = 'unknown'
        if ident == 'C13':
            raw = json.loads((out / 'raw/evidence.json').read_text()); raw['latency']={'samples_ms':[0,1,2], 'sorted':True}
            write_json(out / 'raw/evidence.json',raw)
            inventory = json.loads((out/'sources.json').read_text()); inventory['sources'][0]['role']='engine-terminal-results'
            write_json(out/'sources.json',inventory)
    elif ident in ('C15','H05'):
        for i,row in enumerate(attempts):
            currency='EUR' if ident=='C15' and i==1 else 'USD'
            sid='receipt-'+str(i); path='raw/'+sid+'.json'
            _add_source(out,sid,path,dict(request=row['attempt_id'],amount='0',currency=currency))
            row['cost']=dict(amount='0',currency=currency,kind='observed',scope='attempt',source_ref=sid+'#$')
    elif ident == 'C16':
        window=dict(started_at='2026-10-17T00:00:00Z',ended_at='2026-10-17T01:00:00Z')
        # Both declaration and actual describe the same later run; only allowed window fails.
        for arm in 'ab': p['arms'][arm]['run_window']=window; m['actual_settings'][arm]['run_window']=window
    elif ident == 'C17':
        tasks[0]['gold_ids']={'pmid':['12345678']}
        for row in outcomes + attempts:
            if row['assignment_id'].endswith('t1'):
                row['results']=[dict(outcomes[0]['results'][0],url='https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/')]
                if 'reported_hit_rank' in row: row['reported_hit_rank']=None
        p['conversion_map_sha256']='a'*64
        m['extensions']={'conversion_map':dict(status='unavailable',source_id=None,reason='Required historical map was not retained')}
    elif ident == 'C18':
        (out/'tasks.jsonl').write_text('{"task_id":"t1","task_id":"duplicate"}\n')
        rehash(out)
        return out
    elif ident == 'C19':
        inventory=json.loads((out/'sources.json').read_text()); inventory['sources'][0]['local_path']='../outside.json'
        write_json(out/'sources.json',inventory)
    elif ident == 'C20':
        m.update(origin='new_run',assignment_basis='predeclared',assignment_manifest_frozen_at='2026-10-16T02:00:00Z',assignment_manifest_sha256='0'*64)
    elif ident == 'H02': outcomes[0]['limitations']=['UNKNOWN_JUDGMENT']
    elif ident == 'H06':
        for name in data: data[name].reverse()
    elif ident == 'H08':
        for arm in 'ab':
            m['actual_settings'][arm]['mode']=p['arms'][arm]['mode']='pro' if arm=='b' else 'auto'
        # Hand-derived native metrics, explicitly synthetic; ultimate is a ceiling only.
        gold=out/'raw/gold.jsonl'; write_rows(gold,tasks)
        inventory=json.loads((out/'sources.json').read_text())
        inventory['sources'].append(dict(inventory['sources'][0],source_id='gold',local_path='raw/gold.jsonl',parents=['src']))
        write_json(out/'sources.json',inventory)
        for i,t in enumerate(tasks,1): t['source_ref']='gold#line='+str(i)
        native=dict(discrepancies=[],num_queries=3,engines={a:dict(num_scored=3,recall_at_k=1/3,mrr_at_k=1/3,search_errors=1,per_query_hit_ranks=[1,None,None]) for a in 'ab'},selected_engine_ultimate=dict(recall_at_k=1/3,description='Synthetic native ultimate ceiling'))
        _add_source(out,'native','raw/native.json',native,'native-baseline')
        m['extensions']={'native_profile':'needle-scholar-all-rows-v1','baseline_source_ids':{'native':'native'}}
    elif ident not in ('H01','H04','H07'): raise ValueError(ident)
    for name,rows in data.items(): write_rows(out / (name+'.jsonl'),rows)
    if ident == 'H06':
        for name in data:
            rows = [dict(reversed(list(row.items()))) for row in data[name]]
            (out / (name+'.jsonl')).write_text(''.join(json.dumps(row, sort_keys=False)+'\n' for row in rows))
    write_json(out/'packet.json',m); write_json(out/'protocol.json',p)
    _inventory(out)
    rehash(out)
    return out


def evaluate_validation_input(root: Path):
    """Exercise real import, immutable ledger, oracle, and comparison gates."""
    from pilotpack import ingest, score, compare
    from pilotpack.schema import ValidationError
    stage='import'
    try:
        run=ingest.freeze(root, adapter='canonical',config_path=ROOT/'fixtures/config/canonical.json',
                          protocol_path=root/'protocol.json',sources_path=root/'sources.json',out=root.parent/'run')
        stage='score'
        evaluation=score.score_run(run)
        stage='compare'
        evaluation=compare.assess(ingest.verify_run(run),evaluation)
        return dict(stage=stage,evaluation=evaluation,codes=sorted({d['code'] for d in evaluation['diagnostics']}))
    except ValidationError as error:
        return dict(stage=stage,evaluation=None,codes=sorted({d['code'] for d in error.diagnostics}))


def collect_findings(run_or_input: Path) -> set[str]:
    """Stable diagnostic codes, without implementing selection or scoring."""
    from pilotpack import ingest, score, compare
    from pilotpack.schema import ValidationError
    if (run_or_input/'ledger.sqlite').exists():
        try:
            value=compare.assess(ingest.verify_run(run_or_input),score.score_run(run_or_input))
            return {d['code'] for d in value['diagnostics']}
        except ValidationError as error: return {d['code'] for d in error.diagnostics}
    return set(evaluate_validation_input(run_or_input)['codes'])
