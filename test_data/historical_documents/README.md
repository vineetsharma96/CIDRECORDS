# SYNTHETIC TEST DATA

All people, locations and identifiers are fictional. TEST/SYN values are deliberately non-operational. Account strings retain leading zeros.

Run `python scripts/generate_samples.py` from CID to regenerate. Upload only CSV/PDF files; expected_results.json is a separate test oracle.

Seed six stable profiles first. Run each fixture against a fresh seed for the expected counts. Shared account/address records require Keep Separate approval. Exact and corroborated variants enrich; name-only and contradictions defer. Identifier-only records become unresolved mentions. Reupload the identical bytes to test file idempotency; import the same new person in two different files concurrently to test identity idempotency.

The text PDF has two pages, four people, explicit roles and an explicit meeting statement. The scanned PDF has no selectable text and intentionally substitutes S3n and 0000I; all OCR records require human review even when confidence is high.

Additional fixtures exercise mixed headers, Unicode, and Windows-1252. Blank rows retain only the unmapped synthetic label. Deterministic PDF metadata and raster content support reproducible file hashes.
