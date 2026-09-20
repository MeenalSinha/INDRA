"""
Media (image/video) upload endpoint, with real validation -- this is the
"Image/video upload" data source and the "file upload validation" security
requirement, both implemented for real rather than only simulated via
demo/scenarios.py media_url strings.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..storage import save_media
from ..ai.registry import get_image_analyzer

router = APIRouter(prefix="/api/v1/media", tags=["media"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "video/mp4", "video/quicktime",
}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


@router.post("/upload")
async def upload_media(file: UploadFile = File(...), declared_category: str | None = None):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, f"Unsupported content type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    if len(contents) == 0:
        raise HTTPException(400, "Empty file")

    media_type = "video" if file.content_type.startswith("video/") else "image"
    url = save_media(contents, file.filename or "upload", file.content_type)
    analyzer = get_image_analyzer()
    result = await analyzer.analyze(contents, media_type)
    category, confidence, summary = result.prediction, result.confidence, result.metadata.get("evidence_summary", "")

    return {
        "media_url": url, "media_type": media_type,
        "detected_category": category, "analysis_confidence": confidence,
        "evidence_summary": summary, "size_bytes": len(contents),
    }
