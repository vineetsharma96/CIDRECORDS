"""Local parsing provider. Uploaded prose is data, never executable instructions."""
import csv
import io
import os
import re
from collections import Counter
from typing import Protocol
from app.workspace.matching import FIELDS

HEADER_ALIASES = {"person_name": "name", "full_name": "name", "person": "name", "person_id": "profile_id",
                  "phone_number": "phone", "mobile": "phone", "account_number": "account", "bank_name": "bank",
                  "dob": "birth_date", "date_of_birth": "birth_date", "case_id": "case", "case_reference": "case",
                  "location": "address", "vehicle_number": "vehicle", "organization": "organisation",
                  "caller_number": "caller_phone", "receiver_number": "callee_phone", "callee_number":"callee_phone",
                  "source_account":"from_account", "destination_account":"to_account", "transaction_date":"date", "call_date":"date"}


def header_key(value):
    key = re.sub(r"[^\w]+", "_", str(value).strip().lower()).strip("_")
    return HEADER_ALIASES.get(key, key)


class ExtractionProvider(Protocol):
    def parse(self, filename: str, data: bytes) -> dict: ...


class LocalProvider:
    def parse(self, filename, data):
        return parse_pdf(data) if filename.lower().endswith(".pdf") else parse_csv(data)


def parse_csv(data):
    if b"\x00" in data and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("CSV contains binary data. Export a UTF-8 CSV and retry.")
    encoding = None
    for candidate in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            text = data.decode(candidate)
            encoding = candidate
            break
        except (UnicodeError, LookupError):
            continue
    if encoding is None:
        raise ValueError("CSV encoding is unsupported. Export a UTF-8 CSV and retry.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
    headers = reader.fieldnames or []
    if not headers or len(set(headers)) != len(headers):
        raise ValueError("CSV needs unique column headers. Rename duplicate columns and retry.")
    mapping = {h: header_key(h) for h in headers if header_key(h) in FIELDS}
    records = []
    previous_line = 1
    for row in reader:
        if len(records) >= 5000:
            raise ValueError("CSV exceeds the 5,000-row limit. Split it into smaller files.")
        if None in row:
            raise ValueError(f"CSV row ending at line {reader.line_num} has extra columns. Check quoted values.")
        records.append({"values": {f: row.get(h) or None for h, f in mapping.items()}, "original": row,
                        "row": len(records)+2, "line_start": previous_line+1, "line_end": reader.line_num,
                        "page": None, "span": None, "method": "csv",
                        "confidence": 1.0, "column_mapping": mapping.copy(), "text": None})
        previous_line = reader.line_num
    return {"records": records, "headers": headers, "mapping": mapping, "encoding": encoding, "pages": [], "warnings": []}


def parse_pdf(data):
    import fitz
    if not data.startswith(b"%PDF-"):
        raise ValueError("The file is not a valid PDF. Export a fresh PDF and retry.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError("PDF is damaged or unreadable. Export a fresh copy and retry.") from exc
    with doc:
        if doc.needs_pass:
            raise ValueError("PDF is encrypted. Upload an authorised, unlocked copy.")
        if len(doc) > 100:
            raise ValueError("PDF exceeds 100 pages. Split it into smaller files.")
        pages = []
        for index, page in enumerate(doc):
            if page.rect.width * page.rect.height > 4_000_000:
                raise ValueError(f'Page {index+1} is too large to process safely. Resize or export it at standard paper dimensions.')
            text = page.get_text(sort=True)
            method, confidence = "text", 1.0
            locations = [{"text": b[4], "bbox": list(b[:4])} for b in page.get_text("blocks") if b[6] == 0]
            if len(re.sub(r"\W", "", text)) < 30:
                import pytesseract
                from PIL import Image
                command = os.getenv("TESSERACT_CMD")
                if command:
                    pytesseract.pytesseract.tesseract_cmd = command
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
                try:
                    result = pytesseract.image_to_data(Image.open(io.BytesIO(pix.tobytes("png"))),
                                                      output_type=pytesseract.Output.DICT, timeout=60)
                except pytesseract.TesseractNotFoundError as exc:
                    from pathlib import Path
                    tessdata = os.getenv('TESSDATA_PREFIX', str(Path(__file__).resolve().parents[3] / '.runtime/tessdata'))
                    if not (Path(tessdata) / 'eng.traineddata').is_file():
                        raise ValueError(f"Page {index+1} needs OCR. Install Tesseract and set TESSERACT_CMD, or provide eng.traineddata through TESSDATA_PREFIX, then retry.") from exc
                    tp = page.get_textpage_ocr(tessdata=tessdata, full=True)
                    text = page.get_text(textpage=tp)
                    locations = [{"text": b[4], "bbox": list(b[:4])} for b in page.get_text('blocks', textpage=tp)]
                    # Embedded MuPDF OCR does not expose confidence. Preserve unknown.
                    confidence = None
                    result = None
                if result is not None:
                    words = [(i, word) for i, word in enumerate(result["text"]) if word.strip()]
                    groups = {}
                    for i, word in words:
                        key = (result["block_num"][i], result["par_num"][i], result["line_num"][i])
                        groups.setdefault(key, []).append(word)
                    text = "\n".join(" ".join(group) for group in groups.values())
                    confs = [float(result["conf"][i]) / 100 for i, _ in words if float(result["conf"][i]) >= 0]
                    confidence = sum(confs) / len(confs) if confs else None
                    locations = [{"text": word, "bbox": [result["left"][i]/2.5, result["top"][i]/2.5,
                                 (result["left"][i]+result["width"][i])/2.5, (result["top"][i]+result["height"][i])/2.5],
                                 "confidence": float(result["conf"][i])/100} for i, word in words]
                method = "ocr"
            if not text.strip():
                raise ValueError(f"Page {index+1} has no readable text. Rescan at higher resolution and retry.")
            pages.append({"number": index+1, "text": text, "method": method, "confidence": confidence, "locations": locations,
                          'width': page.rect.width, 'height': page.rect.height})
    # Repeated headers are retained in pages, excluded only from extraction.
    repeated = Counter(line.strip() for p in pages for line in set(p["text"].splitlines()))
    records = []
    warnings = []
    for page in pages:
        records.extend(extract_labeled_people(page, repeated))
    if not records:
        warnings.append("No labelled people found. Use Correct Extraction to add supported details; no profiles were invented.")
        for page in pages:
            values, spans = {}, {}
            for match in re.finditer(r'(?im)^\s*([\w -]+?)\s*[:=]\s*([^\n;]+)', page['text']):
                field = header_key(match.group(1))
                if field in FIELDS:
                    values[field] = match.group(2).strip()
                    spans[field] = [match.start(2), match.end(2)]
            records.append({"values": values, "original": values.copy(), "page": page["number"], "row": None,
                            "text": page["text"], "span": [0, len(page["text"])], "method": page["method"],
                            "confidence": page["confidence"], "column_mapping": {}, 'field_spans': spans, 'locations':page['locations']})
    return {"records": records, "pages": pages, "headers": [], "mapping": {}, "encoding": None, "warnings": warnings}


def extract_labeled_people(page, repeated):
    # Conservative labelled extraction supports semicolon-delimited historical notes
    # and key:value tables. No proximity-based relationship inference is used.
    text = page["text"]
    starts = list(re.finditer(r"(?im)(?:^|(?<=;))\s*(?:Person|Name|Full Name)\s*[:=]\s*([^;\n]+)", text))
    records = []
    for index, start in enumerate(starts):
        end = starts[index+1].start() if index+1 < len(starts) else len(text)
        section = text[start.start():end]
        values, spans = {"name": start.group(1).strip()}, {"name": [start.start(1), start.end(1)]}
        for match in re.finditer(r"(?im)(?:^|[;\n])\s*([\w -]+?)\s*[:=]\s*([^;\n]+)", section):
            field = header_key(match.group(1))
            if field in FIELDS and field != "name":
                values[field] = match.group(2).strip()
                spans[field] = [start.start()+match.start(2), start.start()+match.end(2)]
        # Case and date headers apply only when explicitly labelled on this page.
        for field in ["case", "date"]:
            if field not in values:
                match = re.search(rf"(?im)^{field}(?: reference)?\s*:\s*([^;\n]+)", text)
                if match:
                    values[field] = match.group(1).strip()
                    spans[field] = [match.start(1), match.end(1)]
        records.append({"values": values, "original": values.copy(), "page": page["number"], "row": None,
                        "text": section, "span": [start.start(), end], "field_spans": spans,
                        "locations": page["locations"], "method": page["method"], "confidence": page["confidence"],
                        "column_mapping": {}})
    return records
