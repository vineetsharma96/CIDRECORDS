"""Conservative, explainable identity comparison. Scores are not probabilities."""
import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

FIELDS = ["profile_id", "name", "aliases", "phone", "account", "bank", "address", "birth_date", "vehicle", "organisation", "case", "date", "role", "source_id", "relationship", "caller_phone", "callee_phone", "from_account", "to_account", "from_bank", "to_bank", "amount", "duration"]
WEIGHTS = {"profile_id": 100, "source_id": 55, "name": 20, "aliases": 15, "phone": 30,
           "account": 30, "address": 10, "birth_date": 35, "vehicle": 25}
AUTO_THRESHOLD = int(os.getenv("MATCH_AUTO_THRESHOLD", "80"))


def normalize(field, value):
    if value is None or not str(value).strip():
        return None
    value = unicodedata.normalize("NFKC", str(value)).strip()
    if field in {"date", "birth_date"}:
        for pattern in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                pass
        return value.casefold()
    if field in {"phone", "account", "vehicle", "caller_phone", "callee_phone", "from_account", "to_account"}:
        cleaned = re.sub(r"[^\w]", "", value).casefold()
        if field in {'phone','caller_phone','callee_phone'} and cleaned.isdigit() and value.strip().startswith('00'):
            cleaned = cleaned[2:]
        return cleaned
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", "", value.casefold())).strip()


def values_for(person, claims):
    values = {"profile_id": {normalize("profile_id", person["id"])}}
    sources = {}
    for cid in person.get("claim_ids", []):
        claim = claims.get(cid)
        if claim and claim.get("active", True):
            if claim['field'] != 'profile_id':
                if claim['field'] == 'aliases':
                    values.setdefault('aliases', set()).update(normalize('name', v) for v in re.split(r'[;,|]', str(claim['value'])))
                else:
                    values.setdefault(claim["field"], set()).add(claim["normalized"])
            sources.setdefault(claim["field"], []).append(cid)
    return values, sources


def compare(record, person, claims):
    known, sources = values_for(person, claims)
    incoming = {k: normalize(k, v) for k, v in record["values"].items()}
    matched, conflicts, missing = [], [], []
    score = 0
    for field, weight in WEIGHTS.items():
        value = incoming.get(field)
        existing = known.get(field, set()) - {None}
        if not value or not existing:
            missing.append(field)
            continue
        match = value in existing
        if field == "name" and not match:
            match = value in known.get("aliases", set()) or any(SequenceMatcher(None, value, other).ratio() >= .88 for other in existing)
            if match:
                weight = 15
        if field == "account" and match:
            # Accounts without corroborating bank context are only weak signals.
            if not incoming.get("bank") or incoming["bank"] not in known.get("bank", set()):
                weight = 10
        if match:
            matched.append(field)
            score += weight
        elif field in {"profile_id", "source_id", "birth_date", "phone", "account", "vehicle"}:
            conflicts.append(field)
            score -= 45 if field in {"profile_id", "birth_date", "source_id"} else 20
    identifiers = set(matched) & {"phone", "account", "vehicle", "birth_date", "source_id"}
    corroborated = "name" in matched and len(identifiers) >= 2
    exact_id = "profile_id" in matched
    safe = (corroborated or exact_id) and not conflicts and score >= AUTO_THRESHOLD
    return {"person_id": person["id"], "name": person["name"], "score": max(0, score),
            "matching": matched, "conflicting": conflicts, "missing": missing,
            "sources": sources, "recommended": "merge" if safe else "review"}


def recommend(record, state):
    values = record["values"]
    candidates = [compare(record, person, state["claims"]) for person in state["people"].values() if person.get("active", True)]
    # Contradictions are retained if any candidate signal exists.
    candidates = [c for c in candidates if c["matching"]]
    candidates.sort(key=lambda c: (-c["score"], c["person_id"]))
    candidates = candidates[:10]
    named = bool(normalize("name", values.get("name")))
    sufficient = named and any(normalize(f, values.get(f)) for f in ["profile_id", "phone", "account", "birth_date", "address", "source_id", "vehicle"])
    uncertain = record.get("method") == "ocr" or record.get("confidence", 1) < .85
    for field in ['birth_date', 'date']:
        raw = values.get(field)
        if raw:
            try:
                datetime.strptime(normalize(field, raw) or '', '%Y-%m-%d')
            except ValueError:
                uncertain = True
    safe = [c for c in candidates if c["recommended"] == "merge"]
    if not named and not any(normalize(k, v) for k,v in values.items()) and record.get('text'):
        action = 'review'
    elif not named:
        action = "unresolved"
    elif uncertain:
        action = "review"
    elif len(safe) == 1 and (len(candidates) == 1 or safe[0]["score"] - candidates[1]["score"] >= 20):
        action = "merge"
    elif candidates or not sufficient:
        action = "review"
    else:
        action = "create"
    return {"action": action, "candidates": candidates, "target": safe[0]["person_id"] if action == "merge" else None,
            "reason": "OCR or extraction uncertainty requires review" if uncertain else "Conservative identity rules; score is not a probability"}
