"""Transactional investigation state with an explicit local-demo adapter.

Neo4j is authoritative in normal mode. A single workspace write lock serializes
reconciliation and makes decisions across concurrent imports deterministic.
"""
import copy
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def empty_state():
    return {"jobs": {}, "people": {}, "claims": {}, "audit": [], "revision": 0}


class SQLiteStore:
    backend = "sqlite-demo"

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO workspace VALUES(1, ?)", (json.dumps(empty_state()),))

    def connection(self):
        conn = sqlite3.connect(self.path, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            state = json.loads(conn.execute("SELECT data FROM workspace WHERE id=1").fetchone()[0])
            yield state
            state["revision"] += 1
            conn.execute("UPDATE workspace SET data=? WHERE id=1", (json.dumps(state, ensure_ascii=False),))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def read(self):
        with self.connection() as conn:
            return json.loads(conn.execute("SELECT data FROM workspace WHERE id=1").fetchone()[0])


class Neo4jStore:
    backend = "neo4j"

    def __init__(self):
        from app.repositories.neo4j_connector import neo4j_connector
        self.driver = neo4j_connector.driver
        self.initialized = False

    def initialize(self):
        if self.initialized:
            return
        if self.driver is None:
            raise RuntimeError("Neo4j driver unavailable. Configure NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD.")
        with self.driver.session() as session:
            for label, key in [("InvestigationWorkspace", "workspace_id"), ("ImportJob", "job_id"),
                               ("SourcedClaim", "claim_id"), ("InvestigationEntity", "entity_id")]:
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE").consume()
            session.run("MERGE (w:InvestigationWorkspace {workspace_id:'historical'}) ON CREATE SET w.data=$data, w.revision=0",
                        data=json.dumps(empty_state())).consume()
        self.initialized = True

    @contextmanager
    def transaction(self):
        self.initialize()
        with self.driver.session() as session:
            tx = session.begin_transaction()
            try:
                # SET obtains an exclusive node lock before the state is read.
                row = tx.run("MATCH (w:InvestigationWorkspace {workspace_id:'historical'}) SET w.revision=w.revision+1 RETURN w.data AS data").single()
                state = json.loads(row["data"])
                yield state
                state["revision"] += 1
                tx.run("MATCH (w:InvestigationWorkspace {workspace_id:'historical'}) SET w.data=$data",
                       data=json.dumps(state, ensure_ascii=False)).consume()
                project(tx, state)
                tx.commit()
            except Exception:
                tx.rollback()
                raise

    def read(self):
        self.initialize()
        with self.driver.session() as session:
            row = session.run("MATCH (w:InvestigationWorkspace {workspace_id:'historical'}) RETURN w.data AS data").single()
            return json.loads(row["data"])


def project(tx, state):
    """Project the same committed state into the existing graph, atomically.

    Only nodes/edges owned by this workflow are removed on undo. Legacy graph
    nodes and relationships are never deleted.
    """
    from app.workspace.service import graph_data
    graph = graph_data(state, limit=100000)
    tx.run("MATCH ()-[r:SUPPORTED_ASSOCIATION]->() WHERE r.workflow='historical' DELETE r").consume()
    tx.run("MATCH (n:InvestigationEntity) WHERE n.workflow='historical' AND NOT n.entity_id IN $ids DETACH DELETE n",
           ids=[n["id"] for n in graph["nodes"]]).consume()
    allowed = {"Person", "Phone", "BankAccount", "Vehicle", "Location", "Organisation", "Case", "Document", "Mention"}
    groups = {}
    for node in graph['nodes']:
        label = node['type']
        if label not in allowed:
            continue
        props = {'name': node['label'], 'workflow': 'historical', 'status': node.get('status', 'unknown')}
        if label == 'Person':
            props.update(person_id=node['id'], person_name=node['label'])
        if label == 'Document':
            props.update(document_id=node['id'], source_info=node['label'])
        groups.setdefault(label, []).append({'id': node['id'], 'props': props})
    for label, rows in groups.items():
        tx.run(f'UNWIND $rows AS row MERGE (n:InvestigationEntity {{entity_id:row.id}}) SET n:{label} SET n += row.props', rows=rows).consume()
    tx.run('UNWIND $edges AS edge MATCH (a:InvestigationEntity {entity_id:edge.source}), (b:InvestigationEntity {entity_id:edge.target}) '
           'MERGE (a)-[r:SUPPORTED_ASSOCIATION {edge_id:edge.id}]->(b) '
           "SET r.workflow='historical', r.kind=edge.label, r.claim_ids=edge.evidence, r.review_state=edge.status, r.date=edge.date, r.dates=edge.dates",
           edges=graph['edges']).consume()
    tx.run('UNWIND $jobs AS job MERGE (j:ImportJob {job_id:job.id}) SET j.status=job.status, j.file_hash=job.hash, j.filename=job.filename',
           jobs=[{k:j[k] for k in ['id','status','hash','filename']} for j in state['jobs'].values()]).consume()
    tx.run('UNWIND $claims AS claim MERGE (c:SourcedClaim {claim_id:claim.id}) SET c.data=claim.data',
           claims=[{'id':c['id'], 'data':json.dumps(c, ensure_ascii=False)} for c in state['claims'].values()]).consume()


def make_store():
    mode = os.getenv("WORKSPACE_BACKEND", "neo4j")
    if mode == "sqlite-demo":
        if os.getenv("DEMO_MODE", "false").lower() != "true":
            raise RuntimeError("sqlite-demo requires DEMO_MODE=true. No automatic database fallback is supported.")
        return SQLiteStore(os.getenv("WORKSPACE_DB", str(Path(__file__).resolve().parents[2] / "data/workspace.sqlite")))
    if mode != "neo4j":
        raise RuntimeError("WORKSPACE_BACKEND must be neo4j or sqlite-demo")
    return Neo4jStore()
