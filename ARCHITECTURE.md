# Architecture

## Original application

React 19 + TypeScript + Vite provide the single-page workspace. Framer Motion handles the entrance transition; CSS handles short panel/drawer transitions. Cytoscape is loaded only when Graph Explorer is opened. Fonts are bundled locally. FastAPI provides a separate `/api` interface; background tasks run synchronous parsing in the thread pool rather than in async request handlers. All uploaded documents are treated as untrusted source content.

The reference project's FastAPI, graph labels, registry services, regex/transformer NLP modules and resolver were inspected read-only. The new implementation uses its conceptual domain, but has independent source files, endpoint contracts and matching logic. It does not import or copy that project's services. The unsafe legacy name-only resolver is never invoked.

## Authoritative transaction

Normal mode persists state on `InvestigationWorkspace` in Neo4j. Each write acquires an exclusive lock by updating the workspace revision before reading the JSON state. Review decisions re-evaluate candidates under that lock, so concurrent commits see one another. State and the graph projection commit together; errors roll back both. Unique constraints protect workspace, import-job, claim and graph-entity identifiers. All values use Cypher parameters; dynamic labels come from a fixed allowlist.

The compact aggregate stores jobs, record revisions, canonical people, immutable original claims and audit events. This is a deliberate local/MVP tradeoff: serial writes and full-state projection provide strong consistency at modest dataset sizes, but need partitioning and a normalised event/claim model for large deployment. There is no calibration claim for the identity score.

The optional `SQLiteStore` uses `BEGIN IMMEDIATE` and a unique workspace row, with identical reconciliation semantics. It is available only when explicitly selected and demo mode is enabled. It is not automatically activated by an unavailable Neo4j database.

## Sources and claims

An `ImportJob` uses a SHA-256-based stable ID. Original upload bytes are stored under a generated job filename, never under a user-provided filesystem path. Imports are bounded to 20 MB, 100 PDF pages and 5,000 CSV rows. Parsing creates records and sourced claims; it does not create canonical people until commit.

Each claim records field, original and corrected values, normalised value, document and import IDs, source filename, page/text span and bounding boxes or CSV row/column/mapping, method, confidence, reviewer, review state and commit status. CSV records additionally preserve logical row and physical line range. Unknown values are not comparison evidence.

Correct Extraction creates a new revision and supersedes previous claims. Original values remain retained. Committing attaches claims to a canonical profile or unresolved mention. Undo removes only that commit's assignments and returns its claims to proposed state; later evidence remains attached. Empty new profiles become inactive instead of erasing their history.

## Graph projection

`InvestigationEntity` nodes receive domain labels Person, Phone, BankAccount, Vehicle, Location, Organisation, Case, Document or Mention. Stable identifier keys include bank context for accounts. `SUPPORTED_ASSOCIATION` edges expose semantic kind, claim IDs, review state and an optional record date. Projections include sourced person/identifier and document connections. Explicit meeting statements link only uniquely resolved endpoints within the import and retain a relationship claim.

Phone/account/date information belongs to the source claim and association; no shared identifier forces a person merge. A graph connection indicates source-supported network structure, not guilt. Edges with multiple sources retain all claim IDs. If sources disagree, claims remain separately inspectable.

Graph endpoints provide bounded neighbours, case/date filters and bounded shortest paths. Degree, connected-component and clustering calculations operate on the returned graph; UI bounds are disclosed. Case grouping and dashboard counts derive from persisted state, not generated client examples.

## Failures and restart

Queued/parsing jobs interrupted by a backend restart are marked failed with a Retry action. Original bytes remain available. Retry reruns local parsing; failed and corrected claims remain auditable. Transactional commits cannot partially assign profiles. Upload-byte persistence and database state are separate operations: a disk error persists a failed job with an actionable explanation.

The current thread-pool worker is appropriate for a local application. Durable workers, cancellation, per-tenant isolation and rate limits are future production work. Uploaded data is never submitted to cloud extraction services. Implement another `ExtractionProvider` only with explicit configuration and a documented handling policy.
