# Implementation Status

## Implemented

- Original CID-root React/TypeScript application, separate from the read-only reference code. One unchanged frontend URL, welcome entrance and all nine workspace views; profile/evidence details use drawers.
- FastAPI import, review, evidence, people, case, dashboard, graph, audit and demo endpoints. Secrets stay in the backend environment.
- Neo4j-authoritative transactions, unique constraints, stable file/job/entity/claim IDs and an atomic sourced graph projection. Explicit optional SQLite demo adapter with no automatic fallback.
- Persisted queued/parsing/review/failed/committed jobs; uploaded bytes, repeat-file hash detection, background local parsing, actionable failures and interrupted-job retries.
- CSV encodings, header aliases, original strings, logical row/physical line ranges, column mapping and preview, blank/duplicate rows, quoted values and leading-zero identifiers.
- Selectable-text and image-only PDFs, page text/coordinates, source-page image previews, local Tesseract OCR, encrypted/damaged-file errors, and mandatory review of OCR identities. Embedded OCR confidence is null because that engine does not expose it.
- Conservative labelled extraction of names/aliases, phones, bank/account details, addresses, dates, vehicles, organisations, cases, roles and explicit meeting statements. Uploaded instructions are never executed.
- Explainable matching, conflicts/missing fields/source links, corroborated enrichments, stable new profiles, unresolved identifier-only mentions and all five review actions.
- Audited commits and reversible claim assignment. Undo / Split preserves original claims, later commits and profile IDs; reviewed split claims can become a separate profile.
- Source-supported roles with unknown defaults. Mentioning a person or connecting them in a graph never classifies them as criminal.
- Searchable graph, bounded expansion/path search, case/date filters, sourced relationships, proposed-state distinction, degree/components/clustering and persisted dashboard counts.
- Actual deterministic synthetic CSVs, text/scanned PDFs, expected results and sample archive download.
- Locally bundled fonts, native scrolling, responsive layout, semantic controls, labelled forms, visible focus, Escape-capable native dialogs, graph keyboard alternatives and reduced motion.

## Verification evidence

- `python -m pytest backend/tests -q`: **27 tests passed**, covering CSV/PDF provenance, exact duplicates, blank preservation, conflicts, shared identifiers, new/unresolved identities, repeated/concurrent imports, transactional rollback, corrections, undo, API upload/retry/validation, sample download, source-page rendering, manual review of unlabelled PDF text and explicitly sourced CDR/transfer events.
- `npm run build`: TypeScript check and Vite production build passed.
- `scripts/integrated_demo.py`: passed against real local Neo4j, including text PDF extraction, OCR correction/approval, separate shared-identifier identities, repeat uploads, dashboard reconciliation and an explicit meeting edge linked to its page-one relationship claim. Report: `tmp/verification/integrated-demo.json`.
- `npm run test:e2e`: **3 browser tests passed**: live upload/commit/profile/graph/evidence/audit with unchanged URL; mobile overflow, keyboard focus and reduced motion; automated WCAG scans across the welcome and every workspace view. These are automated checks, not a full manual assistive-technology assessment.
- Both design references and both generated PDFs were rendered and inspected. Source-reference screenshots and verification screenshots are under ignored `tmp/`.

## Practical limits

- This is a local, single-workspace application. Operator-entered reviewer labels are not authentication. Production identity, RBAC, tenant isolation, retention policies and deployment controls are not implemented.
- Matching scores and the 0.88 name-similarity heuristic are not calibrated probabilities. Source-ID namespaces and complex identity history need stronger deployment-specific rules. National phone country codes are not guessed.
- The local provider deliberately extracts labelled records and explicit supported meeting statements. It is not a general multilingual transformer NLP pipeline, universal table parser, handwriting recogniser, financial-pattern detector or free-form narrative extractor. Unknown mentions remain reviewable. No cloud provider is configured.
- Reference registry/FIR/CDR/financial services are not imported or executed because the user requested an independent implementation. Independent column aliases support profile/registry and labelled case/FIR records. Explicit caller/receiver and source/destination account CSV fields create sourced CALLS and TRANSFERS events without inventing people. Other source-specific schemas need reviewed column mapping or another provider.
- Neo4j uses a serialized workspace aggregate and batched full graph projection. This avoids unsafe concurrent identity merges but is intended for modest local datasets, not high-throughput national records.
- Parsing uses the FastAPI thread pool. Restart interruptions have persisted retry state; a durable multi-worker queue, cancellation and worker leases are not implemented.
- Graph statistics disclose a bounded graph. The default explorer caps at 200 nodes; neighbour and path endpoints have explicit bounds. The directory and evidence UI disclose their current display limits (200 profiles / 500 claims); API pagination is available.
- Temporal record dates are preserved in source claims and graph-filtered records, but interval reasoning about reassigned phone numbers or account ownership is not automated.
- Undo operates at commit scope; subsequent reviewed decisions can split source records. It is not an arbitrary destructive bulk merge/split of existing canonical people.
- No remote deployment, publication or push was performed. Original reference changes present before work were preserved. Its licence could not be independently verified, so its source code was not reused.
