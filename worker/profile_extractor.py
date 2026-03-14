"""
Profile-to-field matching logic.

Reads JSON profile files, maps profile keys to detected form field labels
using fuzzy string matching and optional LLM fallback.
"""

import json
import re
from pathlib import Path
from difflib import SequenceMatcher

ALIAS_MAP: dict[str, list[str]] = {
    "full_name": ["name", "full name", "applicant name", "student name", "candidate name", "patient name"],
    "date_of_birth": ["dob", "date of birth", "birth date", "birthday"],
    "email": ["email", "email address", "e-mail", "email id"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "contact number", "telephone"],
    "address": ["address", "residential address", "permanent address", "postal address", "street address"],
    "gender": ["gender", "sex"],
    "nationality": ["nationality", "citizen"],
    "father_name": ["father name", "father's name", "guardian name"],
    "mother_name": ["mother name", "mother's name"],
    "institution": ["institution", "college", "university", "school", "institute name"],
    "department": ["department", "branch", "discipline", "field of study"],
    "roll_number": ["roll number", "roll no", "enrollment number", "registration number", "student id"],
    "year_of_study": ["year of study", "current year", "semester", "year"],
    "cgpa": ["cgpa", "gpa", "grade", "percentage", "marks"],
    "degree": ["degree", "course", "program", "qualification"],
    "graduation_year": ["graduation year", "year of graduation", "expected graduation", "passing year"],
    "aadhar_number": ["aadhar", "aadhaar", "aadhar number", "uid"],
    "pan_number": ["pan", "pan number", "pan card"],
    "bank_account": ["bank account", "account number", "bank account number"],
    "ifsc_code": ["ifsc", "ifsc code", "bank ifsc"],
    "annual_family_income": ["annual income", "family income", "annual family income", "income"],
    "category": ["category", "caste", "reservation category", "social category"],
    "signature_text": ["signature", "sign"],
}


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _best_profile_key(field_label: str, profile_keys: list[str]) -> str | None:
    """Return the best matching profile key for a given field label."""
    norm_label = _normalize(field_label)

    for key, aliases in ALIAS_MAP.items():
        if key not in profile_keys:
            continue
        for alias in aliases:
            if _normalize(alias) in norm_label or norm_label in _normalize(alias):
                return key

    best_key, best_score = None, 0.0
    for key in profile_keys:
        norm_key = _normalize(key.replace("_", " "))
        score = SequenceMatcher(None, norm_label, norm_key).ratio()
        if score > best_score:
            best_score = score
            best_key = key

    return best_key if best_score >= 0.45 else None


def extract_profile_data(
    profile_paths: list[str],
    field_schema: list[dict],
) -> dict:
    """
    Read JSON profile files and map values to form fields.

    Args:
        profile_paths: List of paths to JSON profile files.
        field_schema: List of detected fields, each with at least a 'label' key.

    Returns:
        {
            "values": { "<field_label>": "<matched_value>", ... },
            "confidence": { "<field_label>": <0.0-1.0>, ... },
            "missing_fields": ["<unmatched_label>", ...]
        }
    """
    merged_profile: dict = {}
    for p in profile_paths:
        path = Path(p)
        if not path.is_file():
            continue
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            merged_profile.update(data)

    profile_keys = list(merged_profile.keys())
    values: dict[str, str] = {}
    confidence: dict[str, float] = {}
    missing: list[str] = []

    for field in field_schema:
        label = field.get("label", "")
        if not label:
            continue

        matched_key = _best_profile_key(label, profile_keys)
        if matched_key and merged_profile.get(matched_key):
            values[label] = str(merged_profile[matched_key])
            norm_label = _normalize(label)
            norm_key = _normalize(matched_key.replace("_", " "))
            confidence[label] = round(
                SequenceMatcher(None, norm_label, norm_key).ratio(), 2
            )
        else:
            missing.append(label)

    return {"values": values, "confidence": confidence, "missing_fields": missing}
