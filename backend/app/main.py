import io
import os
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from app.workspace.extraction import LocalProvider
from app.workspace.store import make_store
from app.workspace.service import InvestigationService, analytics, graph_data, shortest_path
from app.workspace.matching import AUTO_THRESHOLD, FIELDS

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('UPLOAD_DIR', str(ROOT / 'backend/data/uploads'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
store = make_store()
service = InvestigationService(store, LocalProvider())
demo = os.getenv('DEMO_MODE', 'false').lower() == 'true'


@asynccontextmanager
async def lifespan(app):
    try:
        with store.transaction() as state:
            for job in state['jobs'].values():
                if job['status'] in {'queued', 'parsing'}:
                    job.update(status='failed', error='Parsing was interrupted. Use Retry to resume the persisted upload.')
    except Exception:
        # Health and actionable 503 responses remain available when the DB is down.
        pass
    yield


app = FastAPI(title='NULLVERSE Investigation API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type'])


@app.exception_handler(Exception)
async def database_error(request, exc):
    from fastapi.responses import JSONResponse
    if isinstance(exc, KeyError):
        return JSONResponse(status_code=404, content={'detail': 'The requested record does not exist.'})
    if isinstance(exc, ValueError):
        return JSONResponse(status_code=400, content={'detail': str(exc)})
    return JSONResponse(status_code=503, content={'detail': 'Workspace storage is unavailable. Start Neo4j and check backend credentials, then retry.'})


class Review(BaseModel):
    action: str
    target: str | None = None
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)
    corrected: dict[str, str | None] | None = None


class Approval(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


class Mapping(BaseModel):
    mapping: dict[str, str]


@app.get('/api/health')
def health():
    store.read()
    return {'status': 'ready', 'backend': store.backend, 'demo': demo, 'fields': FIELDS,
            'auto_threshold': AUTO_THRESHOLD, 'score_label': 'Weighted score, not probability', 'extraction_provider': 'local-labelled'}


@app.get('/api/dashboard')
def dashboard():
    state = store.read()
    graph = graph_data(state)
    jobs = list(state['jobs'].values())
    pending = sum(not r['committed'] and not r['blank'] and not r['duplicate'] for j in jobs for r in j['records'])
    return {'people': sum(p.get('active', True) for p in state['people'].values()), 'documents': len(jobs),
            'facts': sum(c.get('committed', False) and c.get('active', True) for c in state['claims'].values()),
            'pending': pending, 'relationships': len(graph['edges']), 'nodes': graph['total_nodes'],
            'warnings': sum(j['status'] == 'failed' for j in jobs), 'recent_imports': sorted(jobs, key=lambda j: j['created'], reverse=True)[:5],
            'analytics': analytics(graph), 'backend': store.backend, 'demo': demo, 'revision': state['revision']}


@app.post('/api/imports', status_code=202)
async def upload(background: BackgroundTasks, file: UploadFile = File(...)):
    filename = Path((file.filename or '').replace('\\', '/')).name
    if not filename.lower().endswith(('.csv', '.pdf')):
        raise HTTPException(415, 'Upload a PDF or CSV file.')
    data = await file.read(20*1024*1024+1)
    await file.close()
    if not data or len(data) > 20*1024*1024:
        raise HTTPException(413, 'Choose a non-empty file smaller than 20 MB.')
    job, repeated = service.register(filename, data)
    if not repeated:
        path = DATA / (job['id'] + '.bin')
        try:
            path.write_bytes(data)
        except OSError:
            with store.transaction() as state:
                state['jobs'][job['id']].update(status='failed', error='Upload could not be saved. Check disk space and upload directory permissions.')
            raise
        background.add_task(service.parse, job['id'], data)
    return {'job': job, 'repeated': repeated}


@app.get('/api/imports')
def imports():
    return [{k: v for k, v in job.items() if k not in {'records', 'pages'}} | {'record_count': len(job['records'])}
            for job in sorted(store.read()['jobs'].values(), key=lambda j: j['created'], reverse=True)]


@app.get('/api/imports/{job_id}')
def import_job(job_id: str):
    return service.job(job_id)


@app.post('/api/imports/{job_id}/retry', status_code=202)
def retry(job_id: str, background: BackgroundTasks):
    job = service.job(job_id)
    if job['status'] != 'failed':
        raise HTTPException(409, 'Only failed imports can be retried.')
    path = DATA / (job['id'] + '.bin')
    if not path.is_file():
        raise HTTPException(409, 'Original upload is unavailable. Restore the upload file before retrying.')
    with store.transaction() as state:
        if state['jobs'][job_id]['status'] != 'failed':
            raise HTTPException(409, 'This job is already being retried. Refresh its progress.')
        state['jobs'][job_id].update(status='queued', error=None)
    background.add_task(service.parse, job_id, path.read_bytes())
    return {'status': 'queued'}


@app.get('/api/imports/{job_id}/source')
def source(job_id: str):
    job = service.job(job_id)
    path = DATA / (job['id'] + '.bin')
    if not path.is_file():
        raise HTTPException(404, 'Source file is unavailable.')
    return FileResponse(path, filename=job['filename'], media_type='application/pdf' if job['filename'].lower().endswith('.pdf') else 'text/csv')


@app.get('/api/imports/{job_id}/pages/{page_number}.png')
def source_page(job_id: str, page_number: int):
    import pymupdf
    job = service.job(job_id)
    if not job['filename'].lower().endswith('.pdf'):
        raise HTTPException(400, 'Source page rendering is available for PDF imports only.')
    path = DATA / (job['id'] + '.bin')
    if not path.is_file():
        raise HTTPException(404, 'Original PDF is unavailable.')
    with pymupdf.open(path) as document:
        if page_number < 1 or page_number > len(document):
            raise HTTPException(404, 'Page number is outside the source document.')
        page = document[page_number-1]
        scale = min(1.5, 1800 / max(page.rect.width, page.rect.height))
        data = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')
    return Response(data, media_type='image/png')


@app.put('/api/imports/{job_id}/mapping')
def mapping(job_id: str, body: Mapping):
    service.remap(job_id, body.mapping)
    return service.job(job_id)


@app.post('/api/imports/{job_id}/records/{record_id}/review')
def review(job_id: str, record_id: str, body: Review):
    service.decide(job_id, record_id, body.action, body.target, body.actor, body.reason, body.corrected)
    return service.job(job_id)


@app.post('/api/imports/{job_id}/commit')
def commit(job_id: str, body: Approval):
    return service.commit(job_id, body.actor, body.reason)


@app.post('/api/audit/{event_id}/undo')
def undo(event_id: str, body: Approval):
    service.undo(event_id, body.actor, body.reason)
    return {'status': 'undone'}


@app.get('/api/people')
def people(q: str = '', role: str = '', offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    result = service.people(q, role)
    return {'people': result[offset:offset+limit], 'total': len(result)}


@app.get('/api/people/{person_id}')
def person(person_id: str):
    result = next((p for p in service.people() if p['id'] == person_id), None)
    if result is None:
        raise HTTPException(404, 'Profile not found.')
    return result


@app.get('/api/evidence')
def evidence(q: str = '', limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    claims = [c for c in store.read()['claims'].values() if q.casefold() in str(c).casefold()]
    return {'claims': claims[offset:offset+limit], 'total': len(claims)}


@app.get('/api/evidence/{claim_id}')
def claim(claim_id: str):
    return store.read()['claims'][claim_id]


@app.get('/api/cases')
def cases():
    state = store.read()
    groups = {}
    for claim in state['claims'].values():
        if claim['field'] == 'case' and claim['active'] and claim['committed']:
            item = groups.setdefault(claim['normalized'], {'reference': claim['value'], 'people': set(), 'documents': set(), 'evidence': []})
            if claim['person_id']:
                item['people'].add(claim['person_id'])
            item['documents'].add(claim['document'])
            item['evidence'].append(claim['id'])
    return [{**item, 'people': sorted(item['people']), 'documents': sorted(item['documents'])} for item in groups.values()]


@app.get('/api/graph')
def graph(case: str = '', date_from: str = '', date_to: str = '', proposed: bool = False, limit: int = Query(200, ge=1, le=1000)):
    return graph_data(store.read(), case, date_from, date_to, proposed, limit)


@app.get('/api/graph/neighbors/{entity_id}')
def neighbors(entity_id: str, limit: int = Query(30, ge=1, le=100)):
    graph = graph_data(store.read(), limit=10000)
    adjacent = [e for e in graph['edges'] if entity_id in (e['source'], e['target'])][:limit]
    ids = {entity_id} | {e['source'] for e in adjacent} | {e['target'] for e in adjacent}
    return {'nodes': [n for n in graph['nodes'] if n['id'] in ids], 'edges': adjacent}


@app.get('/api/graph/path')
def path(source: str, target: str, hops: int = Query(6, ge=1, le=10), case: str = '', date_from: str = '', date_to: str = ''):
    return shortest_path(graph_data(store.read(), case, date_from, date_to, limit=10000), source, target, hops)


@app.get('/api/audit')
def events():
    return list(reversed(store.read()['audit']))[:500]


@app.post('/api/demo/seed')
def seed():
    if not demo:
        raise HTTPException(403, 'Synthetic seeding is available only with DEMO_MODE=true.')
    seed_path = ROOT / 'test_data/historical_documents/seed_entities.csv'
    data = seed_path.read_bytes()
    job, repeated = service.register(seed_path.name, data)
    if not repeated:
        (DATA / (job['id']+'.bin')).write_bytes(data)
        service.parse(job['id'], data)
        for record in service.job(job['id'])['records']:
            service.decide(job['id'], record['id'], 'create', None, 'synthetic demo', 'Explicit distinct fictional seed identity')
        service.commit(job['id'], 'synthetic demo', 'Initial fictional seed dataset')
    return {'job': service.job(job['id']), 'repeated': repeated}


@app.get('/api/demo/samples')
def samples():
    if not demo:
        raise HTTPException(403, 'Sample downloads are available only in demo mode.')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / 'test_data/historical_documents').glob('*')):
            if path.is_file() and path.suffix in {'.pdf', '.csv', '.json', '.md'}:
                archive.write(path, path.name)
    stream.seek(0)
    return StreamingResponse(stream, media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="synthetic-sample-files.zip"'})
