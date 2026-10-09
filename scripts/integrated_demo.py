"""Run against live FastAPI/Neo4j; asserts persistence and graph provenance."""
import json
import time
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
client=httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=180)


def call(method,path,**kwargs):
    response=client.request(method,path,**kwargs)
    response.raise_for_status()
    return response.json()


def upload(filename):
    data=(ROOT/'test_data/historical_documents'/filename).read_bytes()
    result=call('POST','/imports',files={'file':(filename,data)})
    jid=result['job']['id']
    for _ in range(180):
        job=call('GET','/imports/'+jid)
        if job['status'] not in {'queued','parsing'}:
            assert job['status']!='failed',job['error']
            return job,result['repeated']
        time.sleep(.5)
    raise AssertionError('Import did not finish within 90 seconds')


def main():
    health=call('GET','/health')
    assert health['backend']=='neo4j'
    seed=call('POST','/demo/seed')
    assert len(seed['job']['records'])==6
    results={}
    for filename in ['historical_case_notes.pdf','scanned_case_notes.pdf','shared_identifiers.csv','cdr_events.csv','financial_events.csv']:
        job,repeated=upload(filename)
        if filename=='scanned_case_notes.pdf':
            assert job['pages'][0]['method']=='ocr'
            assert all(r['recommendation']['action']=='review' for r in job['records'] if not r['committed'])
            record=job['records'][0]
            if not record['committed']:
                corrected={**record['values'],'name':'Mira Sen','phone':'TEST-00001','birth_date':'1988-04-12'}
                call('POST',f"/imports/{job['id']}/records/{record['id']}/review",json={'action':'correct','actor':'Demo Reviewer','reason':'Compared synthetic image against ground truth','corrected':corrected})
                call('POST',f"/imports/{job['id']}/records/{record['id']}/review",json={'action':'merge','target':'SYN-P001','actor':'Demo Reviewer','reason':'Name, phone and birth date corroborated after correction'})
        if filename=='shared_identifiers.csv':
            for record in job['records']:
                if not record['committed']:
                    call('POST',f"/imports/{job['id']}/records/{record['id']}/review",json={'action':'separate','actor':'Demo Reviewer','reason':'Different person; shared account or address alone is not identity'})
        event=call('POST',f"/imports/{job['id']}/commit",json={'actor':'Demo Reviewer','reason':'Reviewed supported historical source evidence'})
        results[filename]=event['result']
        again,is_repeat=upload(filename)
        assert is_repeat and again['id']==job['id']
    concurrent_rows=[{'data_label':'SYNTHETIC TEST DATA','name':'Corin Nera','phone':'TEST-CONCURRENT-001','birth_date':'1984-06-14'},
                     {'data_label':'SYNTHETIC TEST DATA','name':'Corin Nera','phone':'TEST-CONCURRENT-001','birth_date':'1984-06-14','case':'SYN-CONCURRENT'}]
    concurrent_jobs=[]
    for index,row in enumerate(concurrent_rows):
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
        uploaded=call('POST','/imports',files={'file':(f'concurrent-{index}.csv',stream.getvalue().encode())})
        jid=uploaded['job']['id']
        for _ in range(180):
            ready=call('GET','/imports/'+jid)
            if ready['status'] not in {'queued','parsing'}:
                assert ready['status']!='failed',ready['error']
                break
            time.sleep(.25)
        concurrent_jobs.append(jid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda jid:call('POST',f'/imports/{jid}/commit',json={'actor':'Demo Reviewer','reason':'Concurrent corroborated import'}),concurrent_jobs))
    graph=call('GET','/graph?limit=1000')
    assert graph['nodes'] and graph['edges']
    assert all(e['evidence'] for e in graph['edges'])
    meeting=next(e for e in graph['edges'] if e['label']=='MET_WITH')
    proof=call('GET','/evidence/'+meeting['evidence'][0])
    assert proof['field']=='relationship' and proof['page']==1
    people=call('GET','/people?limit=200')['people']
    assert len([p for p in people if p['id']=='SYN-P001'])==1
    assert len([p for p in people if p['name']=='Mira Sen'])==2
    assert len([p for p in people if p['name']=='Corin Nera'])==1
    assert any(e['label']=='CALLS' for e in graph['edges'])
    assert any(e['label']=='TRANSFERS' for e in graph['edges'])
    dashboard=call('GET','/dashboard')
    assert dashboard['people']==len(people)
    summary={'health':health,'imports':results,'dashboard':{k:dashboard[k] for k in ['people','documents','facts','pending','relationships','nodes']},'relationship_evidence':proof['id'],'repeat_uploads':'passed','concurrent_neo4j_imports':'passed'}
    target=ROOT/'tmp/verification/integrated-demo.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
