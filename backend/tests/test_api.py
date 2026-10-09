import importlib
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('WORKSPACE_BACKEND','sqlite-demo')
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('WORKSPACE_DB',str(tmp_path/'api.sqlite'))
    monkeypatch.setenv('UPLOAD_DIR',str(tmp_path/'uploads'))
    import app.main as module
    module=importlib.reload(module)
    with TestClient(module.app,raise_server_exceptions=False) as client:
        yield client


def test_upload_persisted_job_and_source_location(client):
    response=client.post('/api/imports',files={'file':('records.csv',b'Name,Phone,DOB\nTara Neri,0000TEST,1980-01-02\n','text/csv')})
    assert response.status_code==202
    jid=response.json()['job']['id']
    job=client.get('/api/imports/'+jid).json()
    assert job['status']=='review'
    assert job['records'][0]['facts'][0]['row']==2
    repeated=client.post('/api/imports',files={'file':('another-name.csv',b'Name,Phone,DOB\nTara Neri,0000TEST,1980-01-02\n')})
    assert repeated.json()['repeated'] is True
    result=client.post('/api/imports/'+jid+'/commit',json={'actor':'API Tester','reason':'Reviewed source evidence'})
    assert result.status_code==200
    assert result.json()['result']['created']==1
    assert client.get('/api/dashboard').json()['people']==1
    graph=client.get('/api/graph').json()
    assert all(edge['evidence'] for edge in graph['edges'])
    assert client.get('/api/imports/'+jid+'/source').content.startswith(b'Name,Phone')


def test_invalid_file_and_missing_job(client):
    assert client.post('/api/imports',files={'file':('bad.exe',b'binary')}).status_code==415
    assert client.post('/api/imports',files={'file':('blank.csv',b'')}).status_code==413
    assert client.get('/api/imports/not-a-job').status_code==404
    assert client.get('/api/people/not-a-person').status_code==404


def test_actionable_failed_import_and_retry(client):
    response=client.post('/api/imports',files={'file':('damaged.pdf',b'%PDF-invalid')})
    jid=response.json()['job']['id']
    job=client.get('/api/imports/'+jid).json()
    assert job['status']=='failed' and 'PDF' in job['error']
    assert client.post('/api/imports/'+jid+'/retry').status_code==202
    assert client.get('/api/imports/'+jid).json()['status']=='failed'


def test_demo_sample_download_and_seed_idempotency(client):
    first=client.post('/api/demo/seed').json()
    second=client.post('/api/demo/seed').json()
    assert first['job']['id']==second['job']['id'] and second['repeated']
    assert client.get('/api/dashboard').json()['people']==6
    response=client.get('/api/demo/samples')
    assert response.status_code==200 and response.content.startswith(b'PK')


def test_review_validation_undo_and_pdf_image(client):
    source=Path(__file__).resolve().parents[2]/'test_data/historical_documents/historical_case_notes.pdf'
    response=client.post('/api/imports',files={'file':(source.name,source.read_bytes())})
    jid=response.json()['job']['id']
    assert client.get(f'/api/imports/{jid}/pages/1.png').content.startswith(b'\x89PNG')
    assert client.get(f'/api/imports/{jid}/pages/999.png').status_code==404
    record=client.get('/api/imports/'+jid).json()['records'][0]
    review=client.post(f"/api/imports/{jid}/records/{record['id']}/review",json={'action':'create','actor':'','reason':''})
    assert review.status_code==422
    event=client.post('/api/imports/'+jid+'/commit',json={'actor':'API Tester','reason':'Reviewed source identities'}).json()
    before=client.get('/api/evidence').json()['total']
    assert client.post('/api/audit/'+event['id']+'/undo',json={'actor':'API Tester','reason':'Split imported claims'}).status_code==200
    assert client.get('/api/evidence').json()['total']==before
    assert client.get('/api/dashboard').json()['people']==0
