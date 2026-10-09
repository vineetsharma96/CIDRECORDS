"""Immutable source claims, reversible decisions and bounded graph views."""
import copy
import hashlib
import json
import re
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from app.workspace.matching import FIELDS, normalize, recommend


def now():
    return datetime.now(timezone.utc).isoformat()


def stable(kind, value):
    return kind + '-' + uuid.uuid5(uuid.NAMESPACE_URL, str(value)).hex[:20]


def audit(state, action, actor, reason, **details):
    event = {"id": str(uuid.uuid4()), "time": now(), "action": action, "actor": actor, "reason": reason, **details}
    state["audit"].append(event)
    return event


class InvestigationService:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def register(self, filename, data):
        digest = hashlib.sha256(data).hexdigest()
        job_id = stable('IMP', digest)
        with self.store.transaction() as state:
            if job_id in state['jobs']:
                return copy.deepcopy(state['jobs'][job_id]), True
            job = {"id": job_id, "hash": digest, "filename": filename, "created": now(), "status": "queued",
                   "progress": 0, "records": [], "pages": [], "mapping": {}, "headers": [], "warnings": [], "error": None}
            state['jobs'][job_id] = job
            audit(state, 'upload', 'local operator', 'Authorised historical record upload', job_id=job_id)
        return copy.deepcopy(job), False

    def parse(self, job_id, data):
        try:
            with self.store.transaction() as state:
                job = state['jobs'][job_id]
                job.update(status='parsing', progress=15, error=None)
                filename = job['filename']
            parsed = self.provider.parse(filename, data)
            with self.store.transaction() as state:
                job = state['jobs'][job_id]
                job.update(parsed, status='review', progress=100, parsed_at=now())
                seen = set()
                for index, record in enumerate(job['records']):
                    derive_event(record)
                    record['id'] = stable('REC', job_id + ':' + str(index))
                    record['decision'] = None
                    record['person_id'] = None
                    record['committed'] = False
                    key = json.dumps(record['values'], sort_keys=True, ensure_ascii=False)
                    record['duplicate'] = key in seen
                    seen.add(key)
                    record['blank'] = not any(normalize(k, v) for k, v in record['values'].items()) and not record.get('text')
                    record['recommendation'] = recommend(record, state)
                    create_claims(state, job, record)
                audit(state, 'extraction', 'local parser', 'Local parsing completed; proposed claims retained', job_id=job_id)
        except Exception as exc:
            with self.store.transaction() as state:
                state['jobs'][job_id].update(status='failed', progress=0, error=str(exc))

    def remap(self, job_id, mapping):
        if any(field not in FIELDS for field in mapping.values()):
            raise ValueError('Mapping contains an unsupported field.')
        if len(mapping.values()) != len(set(mapping.values())):
            raise ValueError('Map each target field only once.')
        with self.store.transaction() as state:
            job = state['jobs'][job_id]
            if job['status'] != 'review' or not job['headers']:
                raise ValueError('Only uncommitted CSV imports can be mapped.')
            if any(header not in job['headers'] for header in mapping):
                raise ValueError('Mapping contains an unknown source column.')
            job['mapping'] = mapping
            seen = set()
            for record in job['records']:
                if record['committed']:
                    raise ValueError('This import already contains committed records.')
                for cid in record.get('claim_ids', []):
                    state['claims'][cid]['active'] = False
                    state['claims'][cid]['review_state'] = 'superseded'
                record['values'] = {field: record['original'].get(header) or None for header, field in mapping.items()}
                derive_event(record)
                record['column_mapping'] = mapping
                record['blank'] = not any(normalize(k, v) for k, v in record['values'].items())
                key = json.dumps(record['values'], sort_keys=True)
                record['duplicate'] = key in seen
                seen.add(key)
                record['decision'] = None
                record['recommendation'] = recommend(record, state)
                record['correction_version'] = record.get('correction_version', 0) + 1
                create_claims(state, job, record)
            audit(state, 'column_mapping', 'local operator', 'Column mapping reviewed', job_id=job_id, mapping=mapping)

    def decide(self, job_id, record_id, action, target, actor, reason, corrected=None):
        if action not in {'merge', 'separate', 'create', 'defer', 'correct'}:
            raise ValueError('Unsupported review action.')
        if not actor.strip() or not reason.strip():
            raise ValueError('Enter the reviewer name and reason for the decision.')
        with self.store.transaction() as state:
            job = state['jobs'][job_id]
            record = next((r for r in job['records'] if r['id'] == record_id), None)
            if record is None:
                raise KeyError('Record not found')
            if record['committed']:
                raise ValueError('Undo this commit before changing its decision.')
            if action == 'correct':
                if corrected is None or any(k not in FIELDS for k in corrected):
                    raise ValueError('Corrected extraction must use supported fields.')
                for cid in record.get('claim_ids', []):
                    state['claims'][cid].update(active=False, review_state='superseded')
                record['values'] = {k: v for k, v in corrected.items() if v is not None and str(v).strip()}
                derive_event(record)
                record['correction_version'] = record.get('correction_version', 0) + 1
                record['corrected_by'] = actor
                record['confidence'] = 1
                record['method'] = 'human-corrected'
                record['blank'] = not bool(record['values']) and not record.get('text')
                record['recommendation'] = recommend(record, state)
                record['decision'] = None
                create_claims(state, job, record)
            else:
                if action == 'merge' and (target not in state['people'] or not state['people'][target].get('active', True)):
                    raise ValueError('Select an active existing profile to merge into.')
                if action in {'create', 'separate'} and not sufficient_identity(record):
                    raise ValueError('A new profile needs a name and at least one supported identity detail. Defer or correct this mention.')
                record['decision'] = {"action": action, "target": target, "actor": actor, "reason": reason}
            audit(state, action, actor, reason, job_id=job_id, record_id=record_id, target=target)

    def commit(self, job_id, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError('Enter reviewer and commit reason.')
        with self.store.transaction() as state:
            job = state['jobs'][job_id]
            if job['status'] not in {'review', 'committed'}:
                raise ValueError('Finish parsing before committing.')
            changed = []
            result = {"created": 0, "enriched": 0, "deferred": 0, "unresolved": 0, "skipped": 0}
            for record in job['records']:
                if record['committed']:
                    continue
                if record['blank'] or record['duplicate']:
                    result['skipped'] += 1
                    record['committed'] = True
                    record['outcome'] = 'skipped'
                    continue
                proposal = recommend(record, state)  # Re-evaluate under database lock.
                record['recommendation'] = proposal
                decision = record['decision']
                action = decision['action'] if decision else proposal['action']
                target = decision.get('target') if decision else proposal['target']
                if action in {'defer', 'review'}:
                    result['deferred'] += 1
                    record['outcome'] = 'deferred'
                    continue
                if action == 'merge':
                    if target not in state['people'] or not state['people'][target].get('active', True):
                        raise ValueError('Merge target changed. Refresh and review this record again.')
                    person = state['people'][target]
                    result['enriched'] += 1
                elif action in {'create', 'separate'}:
                    if not sufficient_identity(record):
                        raise ValueError('Insufficient identity details for a new profile.')
                    supplied = record['values'].get('profile_id')
                    # A reviewer can deliberately keep same-name identities separate.
                    target = supplied if supplied and supplied not in state['people'] else stable('PER', record['id'])
                    if target in state['people'] and state['people'][target].get('active', True):
                        raise ValueError('Profile ID already exists. Review the matching profile.')
                    person = {"id": target, "name": record['values']['name'], "claim_ids": [], "created": now(), "active": True}
                    state['people'][target] = person
                    result['created'] += 1
                else:
                    person, target = None, None
                    result['unresolved'] += 1
                cids = record['claim_ids']
                for cid in cids:
                    claim = state['claims'][cid]
                    claim.update(person_id=target, review_state='verified' if decision else 'supported', committed=True, active=True,
                                 approved_by=decision['actor'] if decision else actor, approval_reason=decision['reason'] if decision else reason)
                    if person is not None and cid not in person['claim_ids']:
                        person['claim_ids'].append(cid)
                record.update(committed=True, person_id=target, outcome='enriched' if action == 'merge' else 'created' if person else 'unresolved')
                changed.append({"record_id": record['id'], "person_id": target, "claims": cids[:], "new": action in {'create', 'separate'}})
            event = audit(state, 'commit', actor, reason, job_id=job_id, changes=changed, result=result)
            job['status'] = 'review' if any(not r['committed'] for r in job['records']) else 'committed'
            job['last_commit'] = event['id']
            job['result'] = result
            return copy.deepcopy(event)

    def undo(self, event_id, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError('Enter reviewer and undo reason.')
        with self.store.transaction() as state:
            event = next((e for e in state['audit'] if e['id'] == event_id and e['action'] == 'commit'), None)
            if event is None:
                raise KeyError('Commit event not found')
            if event.get('undone'):
                raise ValueError('This commit was already undone.')
            for change in event['changes']:
                for cid in change['claims']:
                    state['claims'][cid].update(committed=False, review_state='proposed', person_id=None)
                    person = state['people'].get(change['person_id'])
                    if person:
                        person['claim_ids'] = [c for c in person['claim_ids'] if c != cid]
                person = state['people'].get(change['person_id'])
                if person and change['new'] and not person['claim_ids']:
                    person['active'] = False
                record = next(r for r in state['jobs'][event['job_id']]['records'] if r['id'] == change['record_id'])
                record.update(committed=False, person_id=None, outcome=None, decision=None)
            event['undone'] = True
            state['jobs'][event['job_id']]['status'] = 'review'
            audit(state, 'undo', actor, reason, commit_id=event_id, job_id=event['job_id'])

    def job(self, job_id):
        state = self.store.read()
        job = copy.deepcopy(state['jobs'][job_id])
        for record in job['records']:
            if not record['committed']:
                record['recommendation'] = recommend(record, state)
            record['facts'] = [state['claims'][cid] for cid in record.get('claim_ids', [])]
        return job

    def people(self, query='', role=''):
        state = self.store.read()
        result = []
        for person in state['people'].values():
            if not person.get('active', True):
                continue
            details = person_detail(person, state)
            if query.casefold() not in json.dumps(details, ensure_ascii=False).casefold():
                continue
            if role and role not in [c['normalized'] for c in details['facts'] if c['field'] == 'role']:
                continue
            result.append(details)
        return result


def sufficient_identity(record):
    values = record['values']
    return bool(normalize('name', values.get('name'))) and any(normalize(k, values.get(k)) for k in ['profile_id', 'phone', 'account', 'birth_date', 'address', 'source_id', 'vehicle'])


def derive_event(record):
    values = record['values']
    record['event'] = None
    if values.get('caller_phone') and values.get('callee_phone'):
        record['event'] = {'kind':'CALLS', 'from_field':'caller_phone', 'to_field':'callee_phone'}
    elif values.get('from_account') and values.get('to_account'):
        record['event'] = {'kind':'TRANSFERS', 'from_field':'from_account', 'to_field':'to_account'}
    if record['event']:
        event = record['event']
        values['relationship'] = f"{event['kind']}: {values[event['from_field']]} → {values[event['to_field']]}"


def create_claims(state, job, record):
    record['claim_ids'] = []
    for field, value in record['values'].items():
        normalized = normalize(field, value)
        if normalized is None:
            continue
        cid = stable('CLM', record['id'] + ':' + field + ':' + str(record.get('correction_version', 0)))
        columns = [h for h, f in record.get('column_mapping', {}).items() if f == field]
        original = record['original'].get(columns[0], value) if columns else record['original'].get(field, value)
        if field == 'relationship' and record.get('event'):
            original = json.dumps(record['original'], ensure_ascii=False)
        claim = {"id": cid, "field": field, "original": original, "value": value, "normalized": normalized,
                 "document": job['id'], "filename": job['filename'], "job_id": job['id'], "record_id": record['id'],
                 "row": record.get('row'), "column": columns[0] if columns else None,
                 "line_start": record.get('line_start'), "line_end": record.get('line_end'),
                 "column_mapping": record.get('column_mapping', {}), "page": record.get('page'),
                 "span": record.get('field_spans', {}).get(field, record.get('span')),
                 "locations": [loc for loc in record.get('locations', []) if str(value) in loc['text'] or loc['text'] in str(value)],
                 "method": record['method'], "confidence": record['confidence'], "review_state": "proposed",
                 "committed": False, "active": True, "person_id": None, "created": now(),
                 "corrected_by": record.get('corrected_by')}
        claim['record_date'] = normalize('date', record['values'].get('date'))
        state['claims'][cid] = claim
        record['claim_ids'].append(cid)


def person_detail(person, state):
    facts = [state['claims'][cid] for cid in person['claim_ids'] if state['claims'][cid].get('active', True) and state['claims'][cid].get('committed')]
    roles = {c['normalized'] for c in facts if c['field'] == 'role'}
    allowed = {'suspect', 'witness', 'victim', 'investigator', 'unknown', 'recorded offender'}
    return {**person, 'facts': facts, 'roles': sorted(roles & allowed) or ['unknown'],
            'source_count': len({c['document'] for c in facts})}


def graph_data(state, case='', date_from='', date_to='', include_proposed=False, limit=200):
    nodes, edges = {}, {}
    def node(nid, label, kind, status='supported'):
        nodes[nid] = {"id": nid, "label": label, "type": kind, "status": status}
    def edge(source, target, label, claim, date=None):
        eid = stable('EDGE', source+target+label)
        data = edges.setdefault(eid, {"id": eid, "source": source, "target": target, "label": label,
                                    "evidence": [], "status": claim['review_state'], "date": date, 'dates': []})
        data['evidence'].append(claim['id'])
        if date and date not in data['dates']:
            data['dates'].append(date)
        if claim['review_state'] == 'proposed':
            data['status'] = 'proposed'
    entity_fields = {'phone': 'Phone', 'account': 'BankAccount', 'vehicle': 'Vehicle', 'address': 'Location',
                     'organisation': 'Organisation', 'case': 'Case', 'caller_phone':'Phone', 'callee_phone':'Phone',
                     'from_account':'BankAccount', 'to_account':'BankAccount'}
    for job in state['jobs'].values():
        for record in job['records']:
            if record['blank'] or record['duplicate'] or (not record['committed'] and not include_proposed):
                continue
            if case and normalize('case', record['values'].get('case')) != normalize('case', case):
                continue
            date = normalize('date', record['values'].get('date'))
            if date_from and (not date or date < date_from):
                continue
            if date_to and (not date or date > date_to):
                continue
            claims = [state['claims'][cid] for cid in record.get('claim_ids', []) if state['claims'][cid].get('active', True)]
            if not claims:
                continue
            pid = record.get('person_id')
            if pid and state['people'].get(pid, {}).get('active', True):
                node(pid, state['people'][pid]['name'], 'Person')
            else:
                pid = stable('MENTION', record['id'])
                node(pid, record['values'].get('name') or 'Unresolved Mention', 'Mention', 'proposed')
            node(job['id'], job['filename'], 'Document')
            endpoints = {}
            for claim in claims:
                edge(pid, job['id'], 'MENTIONED_IN', claim, date)
                kind = entity_fields.get(claim['field'])
                if kind:
                    bank_field = 'from_bank' if claim['field']=='from_account' else 'to_bank' if claim['field']=='to_account' else 'bank'
                    context = normalize('bank', record['values'].get(bank_field)) or 'unknown-bank'
                    key = claim['normalized'] + (':'+context if kind == 'BankAccount' else '')
                    identifier = stable(kind, key)
                    node(identifier, str(claim['value']), kind)
                    endpoints[claim['field']] = identifier
                    edge(pid, identifier, 'ASSOCIATED_WITH' if kind != 'Case' else 'INVOLVED_IN', claim, date)
            if record.get('event'):
                event = record['event']
                proof = next((c for c in claims if c['field']=='relationship'), None)
                if proof and event['from_field'] in endpoints and event['to_field'] in endpoints:
                    edge(endpoints[event['from_field']], endpoints[event['to_field']], event['kind'], proof, date)
            # Explicit meeting statements: only uniquely assigned people in this job
            # can be linked. Ambiguous names never force an endpoint resolution.
            for match in re.finditer(r'(?m)^Relationship:\s*(.+?)\s+met with\s+(.+?)[.]?$', record.get('text') or ''):
                endpoints = []
                for name in match.groups():
                    ids = {r['person_id'] for r in job['records'] if r.get('person_id') and normalize('name', r['values'].get('name')) == normalize('name', name.rstrip('.'))}
                    if len(ids) == 1:
                        endpoints.append(ids.pop())
                if len(endpoints) == 2 and all(endpoint in nodes for endpoint in endpoints):
                    supporting = next((c for c in claims if c['field'] == 'relationship'), None)
                    if supporting:
                        edge(endpoints[0], endpoints[1], 'MET_WITH', supporting, date)
    all_nodes = list(nodes.values())
    all_edges = list(edges.values())
    chosen = all_nodes[:limit]
    ids = {n['id'] for n in chosen}
    return {'nodes': chosen, 'edges': [e for e in all_edges if e['source'] in ids and e['target'] in ids],
            'truncated': len(all_nodes) > limit, 'total_nodes': len(all_nodes)}


def analytics(graph):
    adjacency = defaultdict(set)
    for n in graph['nodes']:
        adjacency[n['id']]
    for e in graph['edges']:
        adjacency[e['source']].add(e['target'])
        adjacency[e['target']].add(e['source'])
    unseen, components = set(adjacency), []
    while unseen:
        first = unseen.pop()
        component, queue = {first}, [first]
        while queue:
            current = queue.pop()
            for other in adjacency[current] & unseen:
                unseen.remove(other)
                component.add(other)
                queue.append(other)
        components.append(sorted(component))
    clustering = {}
    for nid, neighbors in adjacency.items():
        k = len(neighbors)
        links = sum(len(adjacency[n] & neighbors) for n in neighbors) / 2
        clustering[nid] = 2*links/(k*(k-1)) if k > 1 else 0
    names = {n['id']: n['label'] for n in graph['nodes']}
    degrees = sorted([{'id': nid, 'name': names[nid], 'degree': len(neighbors), 'clustering': clustering[nid]} for nid, neighbors in adjacency.items()], key=lambda n: -n['degree'])
    return {'components': components, 'component_count': len(components), 'degree_centrality': degrees,
            'average_clustering': sum(clustering.values()) / max(1, len(clustering)), 'bounded': graph.get('truncated', False)}


def shortest_path(graph, source, target, max_hops=6):
    adjacency = defaultdict(list)
    for edge in graph['edges']:
        adjacency[edge['source']].append((edge['target'], edge))
        adjacency[edge['target']].append((edge['source'], edge))
    queue, seen = deque([(source, [source], [])]), {source}
    while queue:
        current, nodes, edges = queue.popleft()
        if current == target:
            return {'nodes': nodes, 'edges': edges}
        if len(edges) >= max_hops:
            continue
        for other, edge in adjacency[current]:
            if other not in seen:
                seen.add(other)
                queue.append((other, nodes+[other], edges+[edge]))
    return {'nodes': [], 'edges': []}
