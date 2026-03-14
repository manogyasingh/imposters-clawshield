"""
FastAPI worker service that wraps existing Python utilities for the
OpenClaw ClawShield plugin to call over HTTP.

Run: uvicorn worker.server:app --host 127.0.0.1 --port 8100
"""

import os
import sys
import tempfile
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.pdf_processor import pdf_to_images, overlay_text
from utils.llm_helper import detect_form_fields
from utils.config import SARVAM_API_KEY
from worker.profile_extractor import extract_profile_data

app = FastAPI(title="ClawShield Worker", version="1.0.0")

WORKSPACE_ROOT = Path(os.environ.get(
    "CLAWSHIELD_WORKSPACE",
    Path(__file__).resolve().parent.parent / "workspace",
))
DETECT_FIELDS_CACHE: dict[tuple[str, int, int], list[dict]] = {}
EXTRACT_PROFILE_CACHE: dict[str, dict] = {}


def _file_signature(path: Path) -> tuple[str, int, int]:
    resolved = str(path.resolve())
    if not path.exists():
        return (resolved, -1, 0)
    stat = path.stat()
    return (resolved, stat.st_mtime_ns, stat.st_size)


def _extract_profile_cache_key(profile_paths: list[str], field_schema: list[dict]) -> str:
    profile_signatures = [_file_signature(Path(path)) for path in profile_paths]
    payload = {
        "profile_signatures": profile_signatures,
        "field_schema": field_schema,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class DetectFieldsRequest(BaseModel):
    pdf_path: str


class ExtractProfileRequest(BaseModel):
    profile_paths: list[str]
    field_schema: list[dict]


class FillPdfRequest(BaseModel):
    pdf_path: str
    field_values: list[dict]


class TranscribeRequest(BaseModel):
    audio_path: str
    language: str = "en-IN"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/detect-fields")
async def detect_fields_endpoint(req: DetectFieldsRequest):
    pdf_path = Path(req.pdf_path)
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found: {req.pdf_path}")

    cache_key = _file_signature(pdf_path)
    cached_fields = DETECT_FIELDS_CACHE.get(cache_key)
    if cached_fields is not None:
        return {"fields": cached_fields}

    try:
        images = pdf_to_images(str(pdf_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF processing error: {e}")

    all_fields: list[dict] = []
    for page_idx, img in enumerate(images):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            img.save(tmp.name)
            tmp_path = tmp.name

        try:
            fields = detect_form_fields(tmp_path)
            for f in fields:
                f["page"] = page_idx
            all_fields.extend(fields)
        finally:
            os.unlink(tmp_path)

    DETECT_FIELDS_CACHE[cache_key] = all_fields
    return {"fields": all_fields}


@app.post("/extract-profile")
async def extract_profile_endpoint(req: ExtractProfileRequest):
    cache_key = _extract_profile_cache_key(req.profile_paths, req.field_schema)
    cached_result = EXTRACT_PROFILE_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        result = extract_profile_data(req.profile_paths, req.field_schema)
        EXTRACT_PROFILE_CACHE[cache_key] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile extraction error: {e}")


@app.post("/fill-pdf")
async def fill_pdf_endpoint(req: FillPdfRequest):
    pdf_path = Path(req.pdf_path)
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found: {req.pdf_path}")

    staged_dir = WORKSPACE_ROOT / "forms" / "staged"
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staged_dir / f"{pdf_path.stem}_filled.pdf"

    try:
        overlay_text(str(pdf_path), req.field_values, str(staged_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF fill error: {e}")

    return {"staged_path": str(staged_path)}


@app.post("/transcribe")
async def transcribe_endpoint(req: TranscribeRequest):
    if not SARVAM_API_KEY:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")

    audio_path = Path(req.audio_path)
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio not found: {req.audio_path}")

    try:
        from utils.sarvam_helper import transcribe_audio
        text = transcribe_audio(str(audio_path), SARVAM_API_KEY, req.language)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")
