# Matching Rules

## Normalisation and comparison

Original input always remains in its source claim. Unicode NFKC, case folding, whitespace and punctuation normalisation support name and address comparison. Phone punctuation is removed; international `00` and `+` representations are made comparable without guessing a country for national numbers. Account and vehicle strings retain leading zeros. Dates accept ISO, day/month/year, day-month-year and English month names. Unsupported date formats remain sourced text and require review.

Candidates are retrieved from active people with at least one available matching attribute. For this local-scale implementation, retrieval scans sourced attributes; no fuzzy name search alone can approve a merge. Names accept exact/alias matching or sequence similarity of at least 0.88. Multiple aliases may be separated by comma, semicolon or pipe. Internal profile ID comparison uses the canonical ID, not an arbitrary sourced claim's asserted ID.

| Attribute | Agreement Weight |
|---|---:|
| Canonical profile ID | 100 |
| Source identifier | 55 |
| Name | 20 |
| Fuzzy name | 15 |
| Alias | 15 |
| Phone | 30 |
| Account with matching bank | 30 |
| Account without matching bank context | 10 |
| Address | 10 |
| Birth date | 35 |
| Vehicle | 25 |

Conflicting profile ID, birth date or source identifier deducts 45 points. Conflicting available phones, accounts or vehicles deduct 20. Unknown attributes do not agree or conflict. Multiple identifier claims remain separate sourced assertions rather than being overwritten.

`MATCH_AUTO_THRESHOLD` defaults to **80** weighted points. This uncalibrated score is not a probability. Source-specific ID namespaces and temporally reassigned identifiers require more extensive policies for deployment beyond the demo; operator review remains necessary when such contexts are uncertain.

## Decisions

Automatic enrichment requires either the canonical internal ID or a matching name plus at least two independent identity-attribute types, no explicit conflicts, and threshold agreement. A fuzzy name contributes fewer points. A unique safe candidate must lead other candidates by at least 20 points. Matching names, addresses, phones or accounts alone cannot automatically merge people. All OCR records, low-confidence extraction and unsupported dates require review.

A named record with at least one identity detail and no candidate receives a stable new profile at commit. A name-only record requires review. Identifier-only records create identifiers attached to unresolved mentions and never invent a named person. Blank and duplicate rows are skipped while their original record content remains retained.

Reviewers can Merge into an existing profile, Keep Separate, Create New Profile, Defer, or Correct Extraction. Reviewer and reason are mandatory; manual approval can accept a conflicting claim but preserves it beside other sourced information. The reviewer label is local operator input, not an authenticated account. Every approval and commit is audited.

## Commit, concurrency and undo

The preview records recommended or approved changes. Commit re-evaluates unapproved recommendations inside the database lock. An earlier concurrent import can therefore turn a new-person proposal into an enrichment. A repeated file hash returns its existing job; recommitting an already committed record adds no assignments. Deliberate Keep Separate approval creates a distinct canonical person even with a shared identifier.

Commit adds claims and aliases without replacing other sourced values or filling missing fields with fabricated data. Shared accounts include bank context in graph keys. Original source claims and commit events remain immutable in content; assignment/review flags change through audited events.

Undo / Split returns a commit's assigned claims to review, preserves original evidence, and leaves subsequent commits intact. A subsequent Create New Profile or Keep Separate decision splits selected source claims into a new identity. There is no destructive graph-node merge or arbitrary canonical-person-to-person bulk merge endpoint.
