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
from .models import (
    AnswersRequest,
    ContactRequest,
    CreateCaseRequest,
    CreatePortfolioRequest,
    PatchCaseRequest,
)

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


# ----------------------------------------------------------------------
# Portfolios (phase 2)
# ----------------------------------------------------------------------
@app.get("/api/case-studies")
def list_cases():
    """Published case studies, for the portfolio work picker."""
    return {"cases": storage.list_published_cases()}


@app.post("/api/portfolios")
def create_portfolio(req: CreatePortfolioRequest):
    if not req.context.strip():
        raise HTTPException(400, "context is required")
    external = [e.model_dump() for e in req.external]
    pid = storage.create_portfolio(req.context.strip(), req.case_slugs, external)
    p = storage.get_portfolio(pid)
    return {"id": pid, **ai.portfolio_questions(p["context"], p["transcript"])}


@app.post("/api/portfolios/{pid}/answers")
def portfolio_answers(pid: str, req: AnswersRequest):
    p = storage.get_portfolio(pid)
    if not p:
        raise HTTPException(404, "portfolio not found")
    storage.append_portfolio_transcript(pid, "answers", req.answers)
    p = storage.get_portfolio(pid)
    return ai.portfolio_questions(p["context"], p["transcript"])


@app.post("/api/portfolios/{pid}/assets")
async def upload_portfolio_asset(pid: str, file: UploadFile = File(...)):
    p = storage.get_portfolio(pid)
    if not p:
        raise HTTPException(404, "portfolio not found")
    ext = config.ALLOWED_IMAGE_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, f"unsupported image type: {file.content_type}")
    body = await file.read()
    if len(body) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(400, "image too large")

    pdir = config.UPLOAD_DIR / "portfolio" / pid
    pdir.mkdir(parents=True, exist_ok=True)
    ref = uuid.uuid4().hex[:8]
    filename = f"{ref}{ext}"
    (pdir / filename).write_bytes(body)
    asset = {
        "ref": ref, "filename": filename, "path": str(pdir / filename),
        "media_type": file.content_type, "url": f"/uploads/portfolio/{pid}/{filename}",
    }
    storage.add_portfolio_asset(pid, asset)
    return {"asset": {"ref": ref, "url": asset["url"]}}


@app.post("/api/portfolios/{pid}/generate")
def generate_portfolio(pid: str):
    p = storage.get_portfolio(pid)
    if not p:
        raise HTTPException(404, "portfolio not found")

    # Resolve selected case studies to their public cards.
    by_slug = {c["slug"]: c for c in storage.list_published_cases()}
    selected = [by_slug[s] for s in (p.get("case_slugs") or []) if s in by_slug]
    external = p.get("external") or []
    assets = p.get("assets") or []
    avatar = assets[0] if assets else None

    document = ai.generate_portfolio(p["context"], p["transcript"], avatar, selected, external)
    document["asset_urls"] = {a["ref"]: a["url"] for a in assets}

    template = document.get("recommended_template") or config.DEFAULT_TEMPLATE
    if template not in config.TEMPLATES:
        template = config.DEFAULT_TEMPLATE
    theme = document.get("theme")  # portfolios may not have an extracted palette

    slug = storage.save_generated_portfolio(pid, document, template, theme)
    return {
        "slug": slug, "url": f"/p/{slug}", "template": template,
        "recommended_template": template, "template_reason": document.get("template_reason", ""),
        "theme": theme, "templates": config.TEMPLATES,
    }


@app.patch("/api/portfolios/{pid}")
def patch_portfolio(pid: str, req: PatchCaseRequest):
    p = storage.get_portfolio(pid)
    if not p:
        raise HTTPException(404, "portfolio not found")
    if req.template and req.template not in config.TEMPLATES:
        raise HTTPException(400, f"unknown template: {req.template}")
    storage.update_portfolio_presentation(pid, req.template, req.theme)
    p = storage.get_portfolio(pid)
    return {"template": p.get("template"), "theme": p.get("theme")}


@app.get("/api/portfolio/{slug}")
def get_portfolio_by_slug(slug: str):
    p = storage.get_portfolio_by_slug(slug)
    if not p:
        raise HTTPException(404, "portfolio not found")
    return {
        "slug": p.get("slug"), "status": p.get("status"),
        "template": p.get("template") or config.DEFAULT_TEMPLATE, "theme": p.get("theme"),
        "document": p.get("document"), "templates": config.TEMPLATES,
    }


@app.post("/api/portfolio/{slug}/contact")
def contact(slug: str, req: ContactRequest):
    p = storage.get_portfolio_by_slug(slug)
    if not p:
        raise HTTPException(404, "portfolio not found")
    pid = p["id"]
    if not req.body.strip():
        raise HTTPException(400, "message body is required")
    storage.add_message(pid, req.name, req.email, req.body.strip())
    emailed = _send_email(p, req)
    return {"ok": True, "emailed": emailed}


def _send_email(portfolio: dict, req: ContactRequest) -> bool:
    if not config.smtp_enabled():
        return False
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        name = (portfolio.get("document") or {}).get("title", "your portfolio")
        msg["Subject"] = f"New message via {name}"
        msg["From"] = config.SMTP_FROM
        msg["To"] = config.SMTP_TO
        if req.email:
            msg["Reply-To"] = req.email
        msg.set_content(f"From: {req.name} <{req.email}>\n\n{req.body}")
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception:
        return False  # message is already stored; don't fail the request


@app.get("/api/portfolios/{pid}/messages")
def portfolio_messages(pid: str):
    if not storage.get_portfolio(pid):
        raise HTTPException(404, "portfolio not found")
    return {"messages": storage.list_messages(pid)}


@app.get("/api/health")
def health():
    return {
        "status": "ok", "service": "casefolio",
        "ai_enabled": config.ai_enabled(), "smtp_enabled": config.smtp_enabled(),
    }


# ----------------------------------------------------------------------
# Page routes (must be registered before the catch-all static mount)
# ----------------------------------------------------------------------
@app.get("/case/{slug}")
def case_page(slug: str):
    return FileResponse(config.WEB_DIR / "case.html")


@app.get("/builder")
def builder_page():
    return FileResponse(config.WEB_DIR / "builder.html")


@app.get("/portfolio")
def portfolio_builder_page():
    return FileResponse(config.WEB_DIR / "portfolio.html")


@app.get("/p/{slug}")
def portfolio_page(slug: str):
    return FileResponse(config.WEB_DIR / "site.html")


# Serve uploaded images and the frontend.
app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
