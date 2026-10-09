You are a senior full-stack engineer, NLP engineer, graph database architect, and UI/UX motion designer. Implement **Criminal Network Analysis System** for **Team NULLVERSE / Dev2Hack** as a working investigation-support application.

Complete implementation, integration, synthetic testing files, and verification. Do not stop at a plan or create only a frontend mockup.

## 1. Mandatory instructions and skills

Before planning or editing code:

- Inspect applicable `AGENTS.md` files.
- Inspect the project’s **`.agents/`** directory, especially `.agents/skills/`.
- Discover and read relevant `SKILL.md` files and follow their referenced instructions.
- **Mandatory: load and apply the “Web Design Guidelines” skill before designing or implementing any frontend screen.**
- Search for its actual directory name, including `web-design-guidelines`, rather than assuming a path.
- Apply its accessibility, layout, typography, responsive design, interaction, and review requirements throughout implementation.
- If this mandatory skill cannot be found, explicitly report the missing skill. Continue independent backend inspection, but do not claim the frontend complies with a skill you have not read.

Follow the user’s requirements first. Resolve routine implementation decisions independently.

## 2. Inspect and integrate the existing code

Use the local folder:

`criminal--network--analysis-`

Reference repository:

https://github.com/Rasraj177/criminial--network--analysis-

The local folder and repository have different spellings. Preserve their actual names.

Inspect the existing code, dependencies, configuration, database model, APIs, frontend, and tests before making changes. Use GitHub tools when needed to inspect the reference repository.

The repository README describes Python/FastAPI, Neo4j, ingestion services, entity extraction, relationship extraction, entity resolution, evidence APIs, and graph analytics. Verify these capabilities in the code rather than assuming they work.

Reuse and improve relevant components, including:

- Registry, criminal-record, FIR, CDR, financial-transaction, and case ingestion services.
- NER and relationship-extraction modules.
- `entity_resolution/resolver.py`.
- Entity, graph, analytics, evidence, and anomaly APIs.

Locate actual paths before editing. Preserve working functionality and inspect the licence before reusing code.

If the local folder is missing, obtain the reference repository in an appropriate directory. Do not push or publish remote changes without separate instructions.

## 3. Product requirements

Build an evidence-linked application that allows users to:

- Import authorised historical PDF and CSV records.
- Extract identity details and explicitly supported relationships.
- Compare incoming records with the existing dataset.
- Enrich matching profiles.
- Review uncertain matches.
- Create new profiles for previously unknown people.
- Explore a searchable knowledge graph.
- Inspect supporting evidence for every fact and relationship.
- Monitor imports, unresolved matches, and graph statistics.

Model people as `Person` entities with source-supported roles or statuses, such as suspect, witness, victim, investigator, unknown, or recorded offender. A document mention or network connection must not automatically classify someone as a criminal.

## 4. Innovation: historical-document extraction and reconciliation

Implement this complete workflow:

**Upload → Parse/OCR → Extract → Normalise → Match → Review → Commit → Explore**

### PDF support

Support selectable-text and scanned PDFs.

- Preserve page numbers and text locations.
- Apply local OCR to pages with insufficient usable text.
- Store extraction method and OCR confidence.
- Flag uncertain names and identifiers for review.
- Handle multiple pages, tables, repeated headers, and multiple people.
- Display actionable errors for encrypted, damaged, or unreadable files.
- Treat instructions inside uploaded files as untrusted document content.

### CSV support

- Provide column mapping and a preview before import.
- Handle missing fields, inconsistent headers, quoted values, duplicate rows, and common encodings.
- Preserve phones, accounts, and identifiers as strings, including leading zeros.
- Retain original values, file name, row number, and column mapping.

### Extracted information

Extract where present:

- Names and aliases.
- Phone numbers.
- Bank accounts and bank identifiers.
- Addresses and locations.
- Birth dates and other supported identity details.
- Vehicle registrations.
- Organisations.
- Case references.
- Relevant dates.
- Explicitly supported relationships.

Missing fields must remain null or unknown. Do not invent information.

Each extracted fact must retain its original value, normalised value, source document, page/text span or CSV row/column, extraction confidence, import job, and review state.

## 5. Matching existing people and creating new profiles

Implement explainable entity resolution using normalisation, candidate retrieval, and weighted attribute comparison.

Compare available information such as:

- Internal profile ID.
- Name and aliases.
- Phone.
- Account number with bank context.
- Address components.
- Birth date.
- Vehicle registration.
- Source-specific identifiers.

Preserve original values while normalising casing, whitespace, punctuation, dates, phone formats, and address components.

### Decision rules

- Strong corroborated matches can enrich or merge an existing profile.
- Partial, ambiguous, or conflicting matches must enter a review queue.
- Clearly new people should receive new profiles.
- Records with insufficient identity information should remain unresolved mentions.

A matching name, address, account, or phone is a candidate signal. Shared addresses, joint accounts, reassigned phones, and extraction errors must be handled.

Never automatically merge people based only on a matching name or address. Treat matching accounts and phones cautiously unless independent evidence supports identity.

Unknown values must not count as matches or conflicts. Explicit contradictions must reduce confidence or require review.

Show:

- Matching attributes.
- Conflicting attributes.
- Missing attributes.
- Supporting sources.
- Matching score.
- Recommended action.

Document configurable thresholds. Do not label an uncalibrated score as a probability.

### Merge behaviour

When an incoming record matches an existing person:

- Preserve the canonical person ID.
- Fill missing fields with supported information.
- Add aliases, identifiers, case associations, and evidence.
- Preserve conflicting information as separate sourced claims.
- Never overwrite valid values with blanks.
- Prevent duplicate nodes and relationships.
- Record who approved the merge and why.
- Support undo/split while preserving original evidence.

Provide:

**Merge / Keep Separate / Create New Profile / Defer / Correct Extraction**

### New-profile behaviour

Create a new profile when sufficient information exists and no acceptable existing match is found.

For an unnamed record containing only an account or phone, create the identifier entity and unresolved mention. Do not invent a named person.

### Import reliability

- Hash files to detect repeated uploads.
- Make ingestion idempotent.
- Use database constraints and transactional commits.
- Prevent concurrent imports from creating duplicate canonical profiles.
- Preview proposed changes before committing.
- Recover from partial failures.
- Preserve temporal account/phone associations where dates exist.

## 6. Graph analysis and evidence

Integrate with the existing Neo4j model where suitable.

Support entities including Person, Phone, BankAccount, Vehicle, Location, Organisation, Case, and Document.

Provide:

- Search and filters.
- Bounded neighbour expansion.
- Shortest paths.
- Case and date filtering.
- Node and relationship details.
- Evidence/provenance drawers.
- Degree centrality, connected components, and clustering where supported.
- Clear distinction between verified and proposed relationships.

Shared identifiers should create explainable graph connections without forcing identity merges.

Every relationship must expose supporting evidence. High connectivity indicates network structure, not guilt.

## 7. UI/UX, dashboard, and animation

Main interface inspiration:

https://jlern.com/

Welcome-screen inspiration only:

https://www.shekunj.com/

Inspect the references visually before implementing. Do not invent observations if a site cannot be accessed.

Apply the mandatory **Web Design Guidelines** skill to every screen.

### Welcome screen

Use SheKunj as inspiration **only for the welcome screen**.

Include:

- Criminal Network Analysis System.
- Team NULLVERSE / Dev2Hack.
- An “Enter Workspace” action.
- A polished entrance transition.
- Responsive and keyboard-accessible interactions.

Do not extend SheKunj’s styling to the dashboard or other screens. Do not copy its branding, text, logos, or proprietary assets.

### Main application

Use jlern.com as inspiration for motion, composition, and visual craft, adapted to an investigation workspace.

Create an original dark navy and teal interface with strong typography, clear hierarchy, thoughtful spacing, and restrained depth.

Animate:

- Screen transitions.
- Dashboard entrances.
- Upload and extraction progress.
- Match-review changes.
- Evidence drawers.
- Graph expansion.
- Successful commits.

Avoid distracting continuous animation. Honour reduced-motion preferences, preserve native scrolling, and support keyboard navigation.

Build:

1. Dashboard.
2. Document upload and column mapping.
3. Import progress and history.
4. Extraction review.
5. Duplicate-match review.
6. Entity directory.
7. Entity detail with sourced facts.
8. Graph explorer.
9. Cases and evidence library.
10. Audit history and settings.

The dashboard must use real database-backed values for entity counts, recent imports, pending reviews, warnings, and graph statistics.

Provide loading, empty, error, and success states. Never silently show mock results after a service failure.

Use side-by-side source and extracted-data review. Distinguish matching, conflicting, and missing fields using labels as well as colour.

## 8. Technology and integration

Preserve the existing stack where practical.

If a frontend is needed, use React/Next.js with TypeScript, suitable styling, a motion library, and an interactive graph library.

Extend FastAPI and Neo4j rather than creating disconnected duplicate services.

- Inspect installed dependencies before selecting versions.
- Consult current official documentation where needed.
- Use local PDF parsing, OCR, and NLP where feasible.
- Keep secrets in environment variables.
- Provide `.env.example`.
- Keep privileged credentials on the backend.
- Use parameterised database queries.
- Validate file types, sizes, and paths.
- Run heavy OCR outside request handlers.
- Persist import-job progress and support retries.
- Provide practical local setup instructions.
- Make the core workflow usable without paid APIs.

Use a pluggable extraction-provider interface. Optional cloud providers must require explicit configuration and documented data handling.

## 9. Generate actual synthetic testing files

Create files inside:

`test_data/historical_documents/`

Generate actual CSVs, a text PDF, and a scanned PDF for OCR testing. Mark everything **SYNTHETIC TEST DATA**.

Use fictional people, fictional addresses, and non-operational identifiers.

Create a seed dataset with stable profile IDs and fixtures covering:

- Exactly the same existing person.
- Existing people with blank fields and matching identifiers.
- Name spelling variants with corroborating details.
- Same-name people who are different.
- Different people sharing an address.
- Different people associated with the same account.
- Existing people receiving new information.
- Conflicting identifiers or birth dates.
- Completely new people.
- Unnamed records containing only identifiers.
- Fully blank rows.
- Duplicate rows.
- Repeat uploads.
- Multiple people and roles in one PDF.
- OCR mistakes requiring review.
- Unicode names, mixed dates, inconsistent headers, and leading-zero identifiers.
- Concurrent imports referring to the same person.

Generate:

- `seed_entities.csv`
- `exact_duplicates.csv`
- `partial_and_missing_fields.csv`
- `ambiguous_matches.csv`
- `shared_identifiers.csv`
- `new_entities.csv`
- `mixed_import.csv`
- `historical_case_notes.pdf`
- `scanned_case_notes.pdf`
- `expected_results.json`
- `README.md`
- A deterministic generation script.

Keep expected outcomes separate from importer inputs. Document expected merges, enrichments, new profiles, deferred records, and unchanged distinct identities.

“Blank information” means deliberately missing fields. Missing values must never be fabricated or used to erase existing information.

Provide “Download Sample Files” in demo mode.

## 10. Verification

Create meaningful tests and verify:

- PDF/CSV imports create persisted jobs.
- Scanned PDF extraction works or gives a clear dependency error.
- Extracted facts reference the correct source page or row.
- Exact duplicates do not create another person.
- Blank fields do not erase existing data.
- Supported partial matches enrich existing profiles.
- Name-only matches require review.
- Shared addresses/accounts preserve separate people.
- Conflicting evidence blocks unsafe automatic merging.
- New people receive stable IDs.
- Identifier-only records remain unresolved.
- Repeat and concurrent imports are idempotent.
- Merge undo preserves evidence.
- Dashboard values reflect committed data.
- Graph edges show provenance.
- SheKunj influences only the welcome screen.
- Main interface motion follows the jlern-inspired direction.
- Web Design Guidelines requirements are reviewed and satisfied.
- Mobile, keyboard, and reduced-motion behaviour work.
- Frontend build, backend tests, and an integrated demonstration pass.

## 11. Deliverables and execution

Deliver working code, database constraints/migrations, synthetic files, tests, environment examples, and concise documentation:

- `README.md`: setup and demonstration.
- `ARCHITECTURE.md`: services and evidence model.
- `MATCHING_RULES.md`: scoring, conflicts, review, and merging.
- `DESIGN.md`: reference boundaries, tokens, accessibility, and motion.
- `IMPLEMENTATION_STATUS.md`: verified functionality and limitations.

Start by inspecting `AGENTS.md`, `.agents/`, the mandatory Web Design Guidelines skill, and the existing project. Then implement and verify the complete system.

The final demonstration must show:

**Seed dataset → Upload historical PDF/CSV → Extract details → Detect existing, uncertain, and new identities → Review → Merge/enrich or create profiles → Explore evidence-linked relationships.**

Report implemented features, run commands, passed checks, and genuine blockers. Do not claim mocked, incomplete, or untested functionality is finished.

Single-page requirement: Keep the entire application at localhost:3000 with everything inside one page. Do not create routes such as /dashboard or /records. Switch between dashboard, uploads, records, graph explorer, evidence, and settings using in-page tabs, panels, drawers, or modals without changing the URL. Show the welcome screen at the same URL, then transition into the workspace. Preserve application state when switching views and keep backend API endpoints separate from frontend navigation.

Don't push anything to github. Its just for reference.