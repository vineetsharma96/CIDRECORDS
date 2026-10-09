"""Deterministic, non-operational synthetic historical import fixtures."""
import csv
import hashlib
import io
import json
from pathlib import Path
import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'test_data/historical_documents'
FIELDS = ['data_label', 'profile_id', 'name', 'aliases', 'phone', 'account', 'bank', 'address', 'birth_date', 'vehicle', 'organisation', 'case', 'date', 'role', 'source_id']
LABEL = 'SYNTHETIC TEST DATA'


def row(**values):
    return {'data_label': LABEL, **values}


SEED = [
    row(profile_id='SYN-P001', name='Mira Sen', phone='TEST-00001', account='000001TEST', bank='Fictional Harbour Bank', address='12 Imaginary Lane, Fictional Bay', birth_date='1988-04-12', role='witness', case='SYN-CASE-01'),
    row(profile_id='SYN-P002', name='Arin Das', phone='TEST-00002', account='000002TEST', bank='Fictional Harbour Bank', address='8 Invented Road, Fictional Bay', birth_date='1990-11-03', role='suspect', case='SYN-CASE-01'),
    row(profile_id='SYN-P003', name='Mira Sen', phone='TEST-00003', birth_date='2001-09-18', address='91 Imaginary Crescent, Fictional Hill', role='victim', case='SYN-CASE-02'),
    row(profile_id='SYN-P004', name='Léa Borel', phone='TEST-00004', address='12 Imaginary Lane, Fictional Bay', birth_date='1985-02-16', role='investigator', case='SYN-CASE-01'),
    row(profile_id='SYN-P005', name='Noor Rafi', phone='TEST-00005', account='000001TEST', bank='Fictional Harbour Bank', address='20 Fiction Avenue, Fictional Bay', birth_date='1993-07-21', role='unknown', case='SYN-CASE-03'),
    row(profile_id='SYN-P006', name='Eden Rao', phone='TEST-00006', source_id='SYN-REG-006', role='unknown')
]


def write_csv(name, rows, headers=FIELDS, encoding='utf-8'):
    with (DEST / name).open('w', encoding=encoding, newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def pdf_bytes(pages):
    output = io.BytesIO()
    doc = canvas.Canvas(output, pagesize=(595, 842), invariant=1, pageCompression=0)
    doc.setTitle(LABEL + ' - Historical Case Notes')
    doc.setAuthor('Team NULLVERSE / Dev2Hack')
    for number, lines in enumerate(pages, 1):
        doc.setFillColor(HexColor('#112b36'))
        doc.rect(0, 770, 595, 72, fill=1, stroke=0)
        doc.setFillColor(HexColor('#ffffff'))
        doc.setFont('Helvetica-Bold', 15)
        doc.drawString(42, 801, LABEL)
        doc.setFillColor(HexColor('#112b36'))
        doc.setFont('Helvetica-Bold', 18)
        doc.drawString(42, 736, 'Historical Case Notes')
        doc.setFont('Helvetica', 11)
        y = 701
        for line in lines:
            doc.drawString(42, y, line)
            y -= 23
        doc.setFont('Helvetica', 9)
        doc.drawString(42, 45, 'Fictional people and non-operational identifiers. For testing only.')
        doc.drawRightString(553, 45, f'Page {number}')
        doc.showPage()
    doc.save()
    return output.getvalue()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    write_csv('seed_entities.csv', SEED)
    write_csv('exact_duplicates.csv', [SEED[0], SEED[0], SEED[1]])
    write_csv('partial_and_missing_fields.csv', [row(profile_id='SYN-P006', name='Eden Rao', phone='TEST-00006', birth_date='1995-08-09', address='5 Fiction Orchard, Fictional Bay'), row(profile_id='SYN-P001', name='Mira Sen', phone='', birth_date='', vehicle='SYN-VEH-001')])
    write_csv('ambiguous_matches.csv', [row(name='Mira Sen'), row(name='Mira Sen', phone='TEST-00001', birth_date='1970-01-01'), row(name='Mira Senn', phone='TEST-00001', birth_date='12/04/1988'), row(name='Arin Das', phone='TEST-OTHER-002', birth_date='1990-11-03')])
    write_csv('shared_identifiers.csv', [row(name='Ivo Maren', phone='TEST-NEW-007', account='000001TEST', bank='Fictional Harbour Bank', birth_date='1982-06-06'), row(name='Sana Voss', phone='TEST-NEW-008', address='12 Imaginary Lane, Fictional Bay', birth_date='1994-01-17')])
    write_csv('new_entities.csv', [row(name='Tara Nolin', phone='TEST-00009', account='000009TEST', bank='Fictional Harbour Bank', birth_date='1998-12-06', role='witness'), row(name='Émile Vey', phone='TEST-00010', birth_date='06 Dec 1996'), row(phone='TEST-00011', account='000011TEST'), row()])
    write_csv('mixed_import.csv', [SEED[0], row(name='Mira Senn', phone='TEST-00001', birth_date='12/04/1988', address='12 Imaginary Lane, Fictional Bay'), row(name='Mira Sen'), row(name='Oren Vale', phone='TEST-00012', birth_date='1991-06-21', account='000012TEST', bank='Fictional Harbour Bank', case='SYN-CASE-04'), row(phone='TEST-UNNAMED-013', account='000013TEST'), row(), SEED[0]])
    write_csv('unicode_headers.csv', [{'Data Label': LABEL, 'Full Name': 'Zoë Neri', 'Phone Number': 'TEST-00014', 'Account Number': '000014TEST', 'Date of Birth': '21/06/1991', 'Address': '4 Fiction Lane, Fictional Vale'}], headers=['Data Label', 'Full Name', 'Phone Number', 'Account Number', 'Date of Birth', 'Address'])
    write_csv('common_encoding.csv', [row(name='René Sol', phone='TEST-00015', birth_date='1987-02-03')], encoding='cp1252')
    write_csv('cdr_events.csv', [{'data_label':LABEL,'caller_number':'TEST-CALL-001','receiver_number':'TEST-CALL-002','call_date':'2024-04-01','duration':'30','case':'SYN-CDR'}], headers=['data_label','caller_number','receiver_number','call_date','duration','case'])
    write_csv('financial_events.csv', [{'data_label':LABEL,'from_account':'000TEST-FROM','to_account':'000TEST-TO','from_bank':'Fictional Bank A','to_bank':'Fictional Bank B','amount':'25.00','transaction_date':'2024-04-01','case':'SYN-FIN'}], headers=['data_label','from_account','to_account','from_bank','to_bank','amount','transaction_date','case'])
    pages = [
        ['Case: SYN-CASE-01', 'Date: 2024-06-15', 'Person: Mira Sen', 'Role: witness', 'Phone: TEST-00001', 'Birth Date: 1988-04-12', 'Address: 12 Imaginary Lane, Fictional Bay', '', 'Person: Arin Das', 'Role: suspect', 'Phone: TEST-00002', 'Birth Date: 1990-11-03', 'Relationship: Mira Sen met with Arin Das.'],
        ['Case: SYN-CASE-04', 'Date: 2024-07-02', 'Person: Tara Nolin', 'Role: witness', 'Phone: TEST-00009', 'Birth Date: 1998-12-06', 'Account: 000009TEST', 'Bank: Fictional Harbour Bank', '', 'Person: Oren Vale', 'Role: unknown', 'Phone: TEST-00012', 'Birth Date: 1991-06-21']
    ]
    (DEST / 'historical_case_notes.pdf').write_bytes(pdf_bytes(pages))
    scan_source = pdf_bytes([['Case: SYN-CASE-OCR', 'Date: 2024-08-03', 'Person: Mira S3n', 'Role: witness', 'Phone: TEST-0000I', 'Birth Date: 1988-04-12', 'Address: 12 Imaginary Lane, Fictional Bay', '', 'OCR mistakes are deliberate and must be reviewed.']])
    raster_doc = fitz.open(stream=scan_source, filetype='pdf')
    scanned = fitz.open()
    for page in raster_doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        new_page = scanned.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=pix.tobytes('png'))
    scanned.set_metadata({'title': LABEL + ' - Scanned Notes', 'author': 'NULLVERSE'})
    scanned.save(DEST / 'scanned_case_notes.pdf', no_new_id=True)
    raster_doc.close()
    scanned.close()
    expected = {'label': LABEL, 'seed_count': 6,
                'exact_duplicates.csv': {'enriched': 2, 'created': 0, 'skipped': 1},
                'partial_and_missing_fields.csv': {'enriched': 2, 'created': 0, 'preserve_blanks': True},
                'ambiguous_matches.csv': {'review_rows': [2, 3, 5], 'enrich_rows': [4], 'never_name_only_merge': True},
                'shared_identifiers.csv': {'review_rows': [2, 3], 'recommended_review_action': 'separate', 'distinct_people': True},
                'new_entities.csv': {'created': 2, 'unresolved': 1, 'skipped': 1},
                'mixed_import.csv': {'enriched': 2, 'created': 1, 'deferred': 1, 'unresolved': 1, 'skipped': 2},
                'historical_case_notes.pdf': {'people': 4, 'pages': 2, 'explicit_relationship': 'Mira Sen met with Arin Das'},
                'scanned_case_notes.pdf': {'review_required': True, 'correct_name': 'Mira Sen', 'correct_phone': 'TEST-00001'},
                'repeat_upload': 'Same job ID; no duplicate profile or source claims',
                'concurrent_import': 'Serial transaction lock; re-evaluate against committed profiles',
                'undo': 'Return claims to proposed state; preserve original values and audit history'}
    expected['cdr_events.csv'] = {'unresolved':1,'relationship':'CALLS','new_people':0}
    expected['financial_events.csv'] = {'unresolved':1,'relationship':'TRANSFERS','new_people':0}
    (DEST / 'expected_results.json').write_text(json.dumps(expected, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    (DEST / 'README.md').write_text('# SYNTHETIC TEST DATA\n\nAll people, locations and identifiers are fictional. TEST/SYN values are deliberately non-operational. Account strings retain leading zeros.\n\nRun `python scripts/generate_samples.py` from CID to regenerate. Upload only CSV/PDF files; expected_results.json is a separate test oracle.\n\nSeed six stable profiles first. Run each fixture against a fresh seed for the expected counts. Shared account/address records require Keep Separate approval. Exact and corroborated variants enrich; name-only and contradictions defer. Identifier-only records become unresolved mentions. Reupload the identical bytes to test file idempotency; import the same new person in two different files concurrently to test identity idempotency.\n\nThe text PDF has two pages, four people, explicit roles and an explicit meeting statement. The scanned PDF has no selectable text and intentionally substitutes S3n and 0000I; all OCR records require human review even when confidence is high.\n\nAdditional fixtures exercise mixed headers, Unicode, and Windows-1252. Blank rows retain only the unmapped synthetic label. Deterministic PDF metadata and raster content support reproducible file hashes.\n', encoding='utf-8')
    print('Generated', len(list(DEST.glob('*'))), 'synthetic fixtures in', DEST)


if __name__ == '__main__':
    main()
