import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
import pymupdf
from app.workspace.extraction import LocalProvider, parse_csv, parse_pdf
from app.workspace.matching import normalize
from app.workspace.service import InvestigationService, analytics, graph_data, shortest_path
from app.workspace.store import SQLiteStore

FIXTURES = Path(__file__).resolve().parents[2] / 'test_data/historical_documents'


def csv_data(rows):
    stream = io.StringIO()
    keys = sorted({k for row in rows for k in row})
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def ingest(service, filename, data=None):
    data = data if data is not None else (FIXTURES / filename).read_bytes()
    job, repeated = service.register(filename, data)
    if not repeated:
        service.parse(job['id'], data)
    return service.job(job['id'])


@pytest.fixture
def service(tmp_path):
    service = InvestigationService(SQLiteStore(tmp_path / 'workspace.sqlite'), LocalProvider())
    seed = ingest(service, 'seed_entities.csv')
    for record in seed['records']:
        service.decide(seed['id'], record['id'], 'create', None, 'test reviewer', 'Explicit fictional seed identity')
    service.commit(seed['id'], 'test reviewer', 'Seed fictional profiles')
    assert len(service.people()) == 6
    return service


def test_exact_duplicates_and_repeat_upload(service):
    job = ingest(service, 'exact_duplicates.csv')
    event = service.commit(job['id'], 'tester', 'Exact corroborated duplicate evidence')
    assert event['result'] == {'created': 0, 'enriched': 2, 'deferred': 0, 'unresolved': 0, 'skipped': 1}
    assert len(service.people()) == 6
    repeated = ingest(service, 'exact_duplicates.csv')
    assert repeated['id'] == job['id']
    again = service.commit(job['id'], 'tester', 'Repeat commit is idempotent')
    assert not again['changes']


def test_blank_fields_enrich_without_erasing(service):
    job = ingest(service, 'partial_and_missing_fields.csv')
    assert service.commit(job['id'], 'tester', 'Supported partial match')['result']['enriched'] == 2
    mira = next(p for p in service.people() if p['id'] == 'SYN-P001')
    assert any(c['field'] == 'phone' and c['value'] == 'TEST-00001' for c in mira['facts'])
    assert any(c['field'] == 'vehicle' and c['value'] == 'SYN-VEH-001' for c in mira['facts'])
    eden = next(p for p in service.people() if p['id'] == 'SYN-P006')
    assert any(c['field'] == 'birth_date' and c['value'] == '1995-08-09' for c in eden['facts'])


def test_name_only_and_contradictions_block_auto_merge(service):
    job = ingest(service, 'ambiguous_matches.csv')
    assert [r['recommendation']['action'] for r in job['records']] == ['review', 'review', 'merge', 'review']
    assert 'birth_date' in job['records'][1]['recommendation']['candidates'][0]['conflicting']
    event = service.commit(job['id'], 'tester', 'Commit only corroborated matches')
    assert event['result']['enriched'] == 1
    assert event['result']['deferred'] == 3
    assert len(service.people()) == 6


def test_shared_identifiers_keep_distinct_people(service):
    job = ingest(service, 'shared_identifiers.csv')
    assert all(r['recommendation']['action'] == 'review' for r in job['records'])
    for record in job['records']:
        service.decide(job['id'], record['id'], 'separate', None, 'tester', 'Different person with a shared identifier')
    event = service.commit(job['id'], 'tester', 'Shared identifier does not prove identity')
    assert event['result']['created'] == 2
    assert len(service.people()) == 8
    graph = graph_data(service.store.read())
    shared = next(n for n in graph['nodes'] if n['type'] == 'BankAccount' and n['label'] == '000001TEST')
    people = {e['source'] for e in graph['edges'] if e['target'] == shared['id']}
    assert len(people) == 3
    assert all(e['evidence'] for e in graph['edges'])


def test_new_people_and_identifier_only_mentions(service):
    job = ingest(service, 'new_entities.csv')
    event = service.commit(job['id'], 'tester', 'New supported identities')
    assert event['result'] == {'created': 2, 'enriched': 0, 'deferred': 0, 'unresolved': 1, 'skipped': 1}
    assert len(service.people()) == 8
    record = service.job(job['id'])['records'][2]
    assert record['person_id'] is None
    assert record['outcome'] == 'unresolved'
    graph = graph_data(service.store.read())
    assert any(n['type'] == 'Mention' for n in graph['nodes'])


def test_expected_mixed_import(service):
    expected = json.loads((FIXTURES/'expected_results.json').read_text())['mixed_import.csv']
    job = ingest(service, 'mixed_import.csv')
    result = service.commit(job['id'], 'tester', 'Mixed historical import')['result']
    assert result == expected


def test_undo_preserves_claims_and_subsequent_evidence(service):
    job = ingest(service, 'partial_and_missing_fields.csv')
    event = service.commit(job['id'], 'tester', 'Enrichment')
    count = len(service.store.read()['claims'])
    later = ingest(service, 'later.csv', csv_data([{'profile_id':'SYN-P001','name':'Mira Sen','organisation':'Fictional Archive'}]))
    service.commit(later['id'], 'tester', 'Later evidence')
    service.undo(event['id'], 'tester', 'Separate mistaken claims')
    state = service.store.read()
    assert len(state['claims']) > count
    assert all(not state['claims'][cid]['committed'] for change in event['changes'] for cid in change['claims'])
    mira = next(p for p in service.people() if p['id'] == 'SYN-P001')
    assert any(c['field'] == 'organisation' for c in mira['facts'])
    assert not any(c['field'] == 'vehicle' for c in mira['facts'])
    assert all(r['committed'] is False for r in service.job(job['id'])['records'])


def test_concurrent_imports_recompare_under_lock(service):
    records = [{'name':'Rian Tal','phone':'TEST-CONCURRENT-01','birth_date':'1980-01-01','role':'witness'},
               {'name':'Rian Tal','phone':'TEST-CONCURRENT-01','birth_date':'1980-01-01','role':'witness','case':'SYN-CONCURRENT'}]
    jobs = [ingest(service, f'concurrent-{i}.csv', csv_data([record])) for i, record in enumerate(records)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        events = list(pool.map(lambda job: service.commit(job['id'], 'tester', 'Concurrent import'), jobs))
    assert sum(e['result']['created'] for e in events) == 1
    assert sum(e['result']['enriched'] for e in events) == 1
    assert len([p for p in service.people() if p['name']=='Rian Tal']) == 1


def test_atomic_rollback(service):
    original = service.store.read()
    with pytest.raises(RuntimeError):
        with service.store.transaction() as state:
            state['people'].clear()
            raise RuntimeError('Injected partial failure')
    assert service.store.read() == original


def test_csv_encoding_mapping_rows_and_identifiers(service):
    parsed = parse_csv((FIXTURES/'unicode_headers.csv').read_bytes())
    assert parsed['records'][0]['values']['account']=='000014TEST'
    assert parsed['records'][0]['values']['name']=='Zoë Neri'
    assert parsed['records'][0]['row']==2
    assert parse_csv((FIXTURES/'common_encoding.csv').read_bytes())['records'][0]['values']['name']=='René Sol'
    job = ingest(service, 'mapped.csv', b'Full Name,Custom Phone,DOB\nAda Neri,0000TEST,21/06/1991\n')
    service.remap(job['id'], {'Full Name':'name','Custom Phone':'phone','DOB':'birth_date'})
    record = service.job(job['id'])['records'][0]
    assert record['values']['phone']=='0000TEST'
    claim = next(c for c in record['facts'] if c['field']=='phone')
    assert claim['row']==2 and claim['column']=='Custom Phone'
    assert claim['original']=='0000TEST'


def test_csv_quoted_multiline_and_utf16():
    text = 'Name,Address,Phone\n"Zoë Neri","12 Invented Road\nFictional Bay",00001TEST\n'
    parsed = parse_csv(text.encode('utf-16'))
    assert parsed['records'][0]['values']['phone'] == '00001TEST'
    assert 'Fictional Bay' in parsed['records'][0]['values']['address']


def test_pdf_page_and_span_provenance(service):
    job = ingest(service, 'historical_case_notes.pdf')
    assert job['status']=='review'
    assert len(job['pages'])==2 and len(job['records'])==4
    assert [r['page'] for r in job['records']]==[1,1,2,2]
    for record in job['records']:
        name_claim=next(c for c in record['facts'] if c['field']=='name')
        page=job['pages'][name_claim['page']-1]
        start,end=name_claim['span']
        assert page['text'][start:end].strip()==name_claim['original']
    service.commit(job['id'], 'tester', 'Source-supported text PDF identities')
    graph=graph_data(service.store.read())
    meeting=next(e for e in graph['edges'] if e['label']=='MET_WITH')
    source_claim=service.store.read()['claims'][meeting['evidence'][0]]
    assert source_claim['field']=='relationship' and source_claim['page']==1
    filtered=graph_data(service.store.read(),case='SYN-CASE-04',date_from='2024-07-01',date_to='2024-07-03')
    assert filtered['nodes']
    result=shortest_path(graph,'SYN-P001','SYN-P002')
    assert result['edges']
    assert analytics(graph)['component_count']>0


def test_scanned_pdf_ocr_or_actionable_dependency_error():
    raw=(FIXTURES/'scanned_case_notes.pdf').read_bytes()
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        assert not doc[0].get_text().strip()
    try:
        parsed=parse_pdf(raw)
    except ValueError as exc:
        assert 'OCR' in str(exc) and ('TESSERACT_CMD' in str(exc) or 'TESSDATA_PREFIX' in str(exc))
    else:
        assert parsed['pages'][0]['method']=='ocr'
        assert parsed['records'][0]['page']==1
        assert parsed['pages'][0]['locations']


def test_ocr_never_automatically_merges(service):
    job = ingest(service,'ocr.csv',csv_data([{'name':'Mira Sen','phone':'TEST-00001','birth_date':'1988-04-12'}]))
    with service.store.transaction() as state:
        record=state['jobs'][job['id']]['records'][0]
        record['method']='ocr'
        record['confidence']=None
    assert service.job(job['id'])['records'][0]['recommendation']['action']=='review'


def test_correction_retains_original_evidence(service):
    job=ingest(service,'correction.csv',csv_data([{'name':'Mira S3n','phone':'TEST-0000I'}]))
    record=job['records'][0]
    original_ids=[c['id'] for c in record['facts']]
    service.decide(job['id'],record['id'],'correct',None,'tester','Checked source scan',{'name':'Mira Sen','phone':'TEST-00001','birth_date':'1988-04-12'})
    assert all(service.store.read()['claims'][cid]['review_state']=='superseded' for cid in original_ids)
    new=service.job(job['id'])['records'][0]
    name=next(c for c in new['facts'] if c['field']=='name')
    assert name['original']=='Mira S3n' and name['value']=='Mira Sen'


@pytest.mark.parametrize('data',[b'not a pdf',b'%PDF-broken'])
def test_damaged_pdf_error(data):
    with pytest.raises(ValueError,match='PDF'):
        parse_pdf(data)


def test_encrypted_pdf_error():
    doc=pymupdf.open();doc.new_page().insert_text((50,50),'SYNTHETIC TEST DATA')
    data=doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='locked')
    with pytest.raises(ValueError,match='encrypted'):
        parse_pdf(data)


def test_review_requires_actor_and_reason(service):
    job=ingest(service,'ambiguous_matches.csv')
    with pytest.raises(ValueError,match='reviewer'):
        service.decide(job['id'],job['records'][0]['id'],'merge','SYN-P001','','')


def test_normalization_unknown_and_leading_zero():
    assert normalize('name','  MIRA   Sen ')==normalize('name','Mira Sen')
    assert normalize('account','00001-TEST')=='00001test'
    assert normalize('birth_date','12/04/1988')=='1988-04-12'
    assert normalize('name','   ') is None


def test_explicit_cdr_and_transfer_rows_have_provenance(service):
    cdr=ingest(service,'synthetic-cdr.csv',csv_data([{'caller_number':'TEST-CALL-001','receiver_number':'TEST-CALL-002','call_date':'2024-04-01','duration':'30','case':'SYN-CDR'}]))
    financial=ingest(service,'synthetic-transfers.csv',csv_data([{'from_account':'000TEST-FROM','to_account':'000TEST-TO','from_bank':'Fictional Bank A','to_bank':'Fictional Bank B','amount':'25.00','transaction_date':'2024-04-01','case':'SYN-FIN'}]))
    for job in [cdr,financial]:
        assert service.commit(job['id'],'tester','Explicit source event')['result']['unresolved']==1
    graph=graph_data(service.store.read())
    calls=next(e for e in graph['edges'] if e['label']=='CALLS')
    transfers=next(e for e in graph['edges'] if e['label']=='TRANSFERS')
    assert calls['dates']==['2024-04-01']
    for edge in [calls,transfers]:
        claim=service.store.read()['claims'][edge['evidence'][0]]
        assert claim['row']==2 and claim['field']=='relationship'
        assert claim['record_date']=='2024-04-01'
        assert json.loads(claim['original'])
    assert len(service.people())==6  # Event endpoints never invent named people.


def test_unlabelled_pdf_can_be_corrected_and_identifier_pdf_stays_unresolved(service):
    doc=pymupdf.open();page=doc.new_page();page.insert_text((40,50),'SYNTHETIC TEST DATA\nHistorical note with an identity requiring manual extraction.\nFictional witness details are not automatically inferred.')
    job=ingest(service,'unlabelled.pdf',doc.tobytes())
    assert not job['records'][0]['blank']
    assert job['records'][0]['recommendation']['action']=='review'
    service.decide(job['id'],job['records'][0]['id'],'correct',None,'tester','Compared source text',{'name':'Ria Vell','phone':'TEST-MANUAL-001'})
    assert service.job(job['id'])['records'][0]['facts']
    doc2=pymupdf.open();doc2.new_page().insert_text((40,50),'SYNTHETIC TEST DATA\nAccount: 000-TEST-UNNAMED\nBank: Fictional Harbour Bank\nNo named holder is recorded.')
    unnamed=ingest(service,'unnamed.pdf',doc2.tobytes())
    assert unnamed['records'][0]['values']['account']=='000-TEST-UNNAMED'
    assert service.commit(unnamed['id'],'tester','Preserve unresolved account mention')['result']['unresolved']==1
