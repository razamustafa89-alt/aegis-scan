"""
Casefolio API — FastAPI app.

Serves the builder + public case-study pages and exposes the case-study lifecycle:
create -> adaptive interview -> upload screens -> generate -> publish at /case/{slug}.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ai, config, storage
from .models import AnswersRequest, CreateCaseRequest, PatchCaseRequest

app = FastAPI(title="Casefolio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    storage.init_db()


# ----------------------------------------------------------------------
# Case-study lifecycle
# ----------------------------------------------------------------------
@app.post("/api/case-studies")
def create_case(req: CreateCaseRequest):
    if not req.context.strip():
        raise HTTPException(400, "context is required")
    case_id = storage.create_case(req.context.strip())
    case = storage.get_case(case_id)
    result = ai.next_questions(case["context"], case["transcript"])
    return {"id": case_id, **result}


@app.post("/api/case-studies/{case_id}/answers")
def submit_answers(case_id: str, req: AnswersRequest):
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    storage.append_transcript(case_id, "answers", req.answers)
    case = storage.get_case(case_id)
    return ai.next_questions(case["context"], case["transcript"])


@app.post("/api/case-studies/{case_id}/assets")
async def upload_asset(case_id: str, file: UploadFile = File(...)):
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    if len(case.get("assets") or []) >= config.MAX_IMAGES_PER_CASE:
        raise HTTPException(400, "too many images for this case")

    ext = config.ALLOWED_IMAGE_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, f"unsupported image type: {file.content_type}")

    body = await file.read()
    if len(body) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(400, "image too large")

    case_dir = config.UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    ref = uuid.uuid4().hex[:8]
    filename = f"{ref}{ext}"
    path = case_dir / filename
    path.write_bytes(body)

    asset = {
        "ref": ref,
        "filename": filename,
        "path": str(path),
        "media_type": file.content_type,
        "url": f"/uploads/{case_id}/{filename}",
        "original_name": file.filename,
    }
    assets = storage.add_asset(case_id, asset)
    return {"asset": {k: asset[k] for k in ("ref", "url", "original_name")}, "count": len(assets)}


@app.post("/api/case-studies/{case_id}/generate")
def generate(case_id: str):
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")

    assets = case.get("assets") or []
    vision = ai.caption_images(assets)
    document = ai.generate_case_study(case["context"], case["transcript"], vision)

    # Map asset refs -> public URLs so the renderer can resolve images.
    document["asset_urls"] = {a["ref"]: a["url"] for a in assets}

    template = document.get("recommended_template") or config.DEFAULT_TEMPLATE
    if template not in config.TEMPLATES:
        template = config.DEFAULT_TEMPLATE
    theme = vision.get("theme")

    slug = storage.save_generated(case_id, document, template, theme)
    return {
        "slug": slug,
        "url": f"/case/{slug}",
        "template": template,
        "recommended_template": template,
        "template_reason": document.get("template_reason", ""),
        "theme": theme,
        "templates": config.TEMPLATES,
    }


@app.patch("/api/case-studies/{case_id}")
def patch_case(case_id: str, req: PatchCaseRequest):
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    if req.template and req.template not in config.TEMPLATES:
        raise HTTPException(400, f"unknown template: {req.template}")
    storage.update_presentation(case_id, req.template, req.theme)
    case = storage.get_case(case_id)
    return {"template": case.get("template"), "theme": case.get("theme")}


@app.get("/api/case-studies/{case_id}")
def get_case(case_id: str):
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return _public_case(case)


@app.get("/api/case/{slug}")
def get_case_by_slug(slug: str):
    case = storage.get_case_by_slug(slug)
    if not case:
        raise HTTPException(404, "case not found")
    return _public_case(case)


def _public_case(case: dict) -> dict:
    return {
        "id": case["id"],
        "slug": case.get("slug"),
        "status": case.get("status"),
        "template": case.get("template") or config.DEFAULT_TEMPLATE,
        "theme": case.get("theme"),
        "document": case.get("document"),
        "templates": config.TEMPLATES,
        "assets": [{"ref": a["ref"], "url": a["url"]} for a in (case.get("assets") or [])],
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "casefolio", "ai_enabled": config.ai_enabled()}


# ----------------------------------------------------------------------
# Page routes (must be registered before the catch-all static mount)
# ----------------------------------------------------------------------
@app.get("/case/{slug}")
def case_page(slug: str):
    return FileResponse(config.WEB_DIR / "case.html")


@app.get("/builder")
def builder_page():
    return FileResponse(config.WEB_DIR / "builder.html")


# Serve uploaded images and the frontend.
app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
