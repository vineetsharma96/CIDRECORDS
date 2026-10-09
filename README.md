# Criminal Network Analysis System

An original evidence-linked investigation workspace for **Team NULLVERSE / Dev2Hack**, built in the CID root. `criminial--network--analysis-` is a read-only reference project; this application neither runs nor imports its code.

The React/TypeScript interface lives at **http://localhost:3000/**. The welcome screen, dashboard, imports, matching, directory, graph, evidence, cases, audit and settings are in-page views. Switching views does not change the URL and preserves the selected import, filters and review inputs.

## Local setup

Use Node 20.19+ or 22.12+, Python 3.12, and Neo4j Community. The development server listens only on the local machine.

```powershell
python -m venv venv
./venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm install
Copy-Item .env.example .env
```

Set `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` in `.env` to your local database. Start Neo4j, then run the API and frontend in separate terminals:

```powershell
./venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
npm run dev
```

The Vite proxy keeps browser API calls under `/api`; backend documentation is at `http://127.0.0.1:8000/docs`. Database constraints initialise automatically and are also supplied in `backend/migrations/001_constraints.cypher`. A database failure returns an actionable service error, never synthetic graph data.

To use the explicitly labelled offline demo, set `WORKSPACE_BACKEND=sqlite-demo` and `DEMO_MODE=true` in `.env`. SQLite has the same transactional review workflow; it does not claim to be Neo4j. Do not use this opt-in mode as a silent production fallback.

## Local OCR

PDF text parsing uses PyMuPDF. Scanned pages use Tesseract: install its executable locally and set `TESSERACT_CMD`, or use PyMuPDF's embedded OCR with local English language data:

```powershell
New-Item -ItemType Directory -Force .runtime/tessdata
Invoke-WebRequest https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata -OutFile .runtime/tessdata/eng.traineddata
```

Alternatively set `TESSDATA_PREFIX` to your language-data directory. Without OCR dependencies, scanned imports persist as failed jobs with installation and retry instructions. Embedded OCR does not expose confidence; the application stores null and displays “unavailable”. All OCR identities require review. No cloud extraction provider is enabled.

## Demonstration

1. Open `localhost:3000`, enter the workspace, and choose **Load Synthetic Seed Dataset** in Settings. Six fictional, distinct profiles receive stable IDs.
2. Download the sample archive or choose files from `test_data/historical_documents/`.
3. Import `mixed_import.csv`. Inspect the CSV mapping, original rows and extracted facts. Enter a reviewer and a reason. Preview safe enrichments, a new profile, a name-only match and an unnamed identifier mention.
4. Commit reviewed changes. Corroborated profiles enrich; name-only matches stay in review. Use Merge, Keep Separate, Create New Profile, Defer or Correct Extraction for unresolved decisions.
5. Import `historical_case_notes.pdf`. Inspect the actual source-page images beside extracted facts; commit the supported identities. Import the scanned PDF, correct its deliberate OCR mistakes, approve its match and commit.
6. Open Graph Explorer, inspect an association and its supporting evidence. Use bounded neighbour expansion or shortest paths. Case and date filters limit the graph.
7. Use Audit History → Undo / Split to return a commit's claims to review while retaining the source evidence and later commits.

`shared_identifiers.csv` intentionally requires Keep Separate decisions: shared addresses and accounts create graph connections without identity merges. Uploaded file hashes deduplicate repeat uploads. Fully blank and duplicate rows remain traceable and are skipped at commit.

## Verification

```powershell
./venv/Scripts/python.exe scripts/generate_samples.py
./venv/Scripts/python.exe -m pytest backend/tests -q
npm run build
npx playwright install chromium
npm run test:e2e
./venv/Scripts/python.exe scripts/integrated_demo.py
```

Browser tests and the integrated demonstration expect both local services to be running with Neo4j and `DEMO_MODE=true`. They add fictional demo records; they do not clear your database. Run fixture count assertions against a fresh seeded workspace. Unit/API tests use isolated temporary SQLite databases. Verification screenshots and the live demonstration report are written under ignored `tmp/verification/`.

The deterministic generator produces actual CSVs, a selectable-text PDF, and an image-only PDF. `expected_results.json` is a separate oracle and is not fed to the importer.

## Boundaries

This is a local investigation-support application, not a production police-record deployment. Reviewer names are operator-entered, not authenticated identities. Do not expose the API publicly or use sensitive operational records until authentication, authorisation, deployment hardening and retention controls are implemented. Current extraction deliberately targets labelled historical records; arbitrary narrative NLP and complex table layouts need a stronger provider and human validation. See `IMPLEMENTATION_STATUS.md` for precise supported behaviour and limits.

No source code from the reference repository was copied. Its README claims MIT licensing but a licence file could not be verified; no upstream licence has been asserted for this original application. Dependency and font licences remain with their packages.
