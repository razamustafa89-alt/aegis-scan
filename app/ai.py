"""
Casefolio — Anthropic client wrapper.

Three capabilities, each returning validated structured data via Claude tool-use:
  * next_questions()      — adaptive interview
  * caption_images()      — vision captions + brand-palette extraction
  * generate_case_study() — the full block document

If no API key is configured (or the SDK/network is unavailable) we fall back to
a deterministic heuristic so the whole flow still works for local demos. The
fallback is clearly labelled in responses via `engine`.
"""

import base64
from typing import Any, Optional

from . import config
from .models import CASE_TOOL, QUESTIONS_TOOL, VISION_TOOL
from .prompts import INTERVIEW_SYSTEM, VISION_SYSTEM, generation_system


# ----------------------------------------------------------------------
# Low-level Claude call
# ----------------------------------------------------------------------
def _call_tool(system: str, content: Any, tool: dict) -> dict[str, Any]:
    """Run one tool-forced message turn and return the tool input dict."""
    import anthropic  # imported lazily so the app boots without the dep at rest

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": content}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            return dict(block.input)
    raise RuntimeError("Model did not return the expected tool call")


def _transcript_text(context: str, transcript: list[dict]) -> str:
    lines = [f"PROJECT CONTEXT:\n{context}\n"]
    for turn in transcript:
        if turn.get("role") == "answers":
            for q, a in (turn.get("content") or {}).items():
                if a and a.strip():
                    lines.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(lines)


# ----------------------------------------------------------------------
# 1) Interview
# ----------------------------------------------------------------------
def next_questions(context: str, transcript: list[dict]) -> dict[str, Any]:
    rounds = sum(1 for t in transcript if t.get("role") == "answers")
    if not config.ai_enabled():
        return _fallback_questions(rounds)
    try:
        text = _transcript_text(context, transcript)
        out = _call_tool(INTERVIEW_SYSTEM, text, QUESTIONS_TOOL)
        out.setdefault("questions", [])
        out.setdefault("ready", not out["questions"])
        return out
    except Exception as exc:  # network / SDK / quota — degrade gracefully
        fb = _fallback_questions(rounds)
        fb["note"] = f"AI unavailable ({exc.__class__.__name__}); using built-in questions."
        return fb


# ----------------------------------------------------------------------
# 2) Vision: captions + palette
# ----------------------------------------------------------------------
def caption_images(assets: list[dict]) -> dict[str, Any]:
    if not assets:
        return {"images": [], "theme": _default_theme()}
    if not config.ai_enabled():
        return _fallback_vision(assets)
    try:
        content: list[dict] = [
            {
                "type": "text",
                "text": "Describe these screens and extract a brand palette. The ref for each "
                "image is given just before it.",
            }
        ]
        for a in assets:
            content.append({"type": "text", "text": f"ref: {a['ref']}"})
            content.append(_image_block(a))
        out = _call_tool(VISION_SYSTEM, content, VISION_TOOL)
        out.setdefault("images", [])
        out.setdefault("theme", _default_theme())
        return out
    except Exception:
        return _fallback_vision(assets)


def _image_block(asset: dict) -> dict:
    with open(asset["path"], "rb") as fh:
        data = base64.standard_b64encode(fh.read()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": asset["media_type"], "data": data},
    }


# ----------------------------------------------------------------------
# 3) Generation
# ----------------------------------------------------------------------
def generate_case_study(
    context: str, transcript: list[dict], vision: dict[str, Any]
) -> dict[str, Any]:
    image_meta = vision.get("images", [])
    theme = vision.get("theme") or _default_theme()
    image_notes = "\n".join(
        f"- ref={i.get('ref')} | section={i.get('suggested_section','solution')} | {i.get('caption','')}"
        for i in image_meta
    )
    theme_hint = ", ".join(f"{k}={v}" for k, v in theme.items())

    if not config.ai_enabled():
        return _fallback_document(context, transcript, image_meta, theme)
    try:
        text = _transcript_text(context, transcript)
        system = generation_system(image_notes, theme_hint)
        doc = _call_tool(system, text, CASE_TOOL)
        doc.setdefault("blocks", [])
        doc.setdefault("recommended_template", config.DEFAULT_TEMPLATE)
        return doc
    except Exception:
        return _fallback_document(context, transcript, image_meta, theme)


# ======================================================================
# Deterministic fallbacks (no API key / offline)
# ======================================================================
def _default_theme() -> dict[str, Any]:
    return {
        "primary": "#2C2C2C",
        "accent": "#FF5A5F",
        "bg": "#FFFFFF",
        "surface": "#F7F7F7",
        "text": "#1A1A1A",
        "mode": "light",
    }


def _fallback_questions(rounds: int) -> dict[str, Any]:
    if rounds >= 1:
        return {"ready": True, "questions": [], "engine": "fallback"}
    return {
        "ready": False,
        "engine": "fallback",
        "questions": [
            {"id": "role", "question": "What was your specific role and who else was on the team?",
             "why": "Recruiters look for ownership.", "placeholder": "Lead product designer; 1 PM, 2 engineers"},
            {"id": "problem", "question": "What problem were you solving, and for whom?",
             "why": "Frames the whole story.", "placeholder": "Hosts struggled to..."},
            {"id": "process", "question": "Walk through your process and 1-2 key design decisions.",
             "why": "Shows how you think.", "placeholder": "Research -> flows -> tested 3 concepts..."},
            {"id": "outcome", "question": "What were the results? Any numbers or feedback?",
             "why": "Proof it worked.", "placeholder": "+18% conversion, shipped Q3"},
            {"id": "tools", "question": "Tools, timeline, and platform?",
             "why": "Quick context.", "placeholder": "Figma, 6 weeks, iOS"},
        ],
    }


def _fallback_vision(assets: list[dict]) -> dict[str, Any]:
    images = [
        {"ref": a["ref"], "caption": f"Screen {i + 1}", "suggested_section": "solution"}
        for i, a in enumerate(assets)
    ]
    return {"images": images, "theme": _default_theme(), "engine": "fallback"}


def _answer_lookup(transcript: list[dict]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for t in transcript:
        if t.get("role") == "answers":
            for q, a in (t.get("content") or {}).items():
                if a and a.strip():
                    merged[q.lower()] = a.strip()
    return merged


def _find(ans: dict[str, str], *keywords: str) -> str:
    for q, a in ans.items():
        if any(k in q for k in keywords):
            return a
    return ""


def _fallback_document(
    context: str, transcript: list[dict], image_meta: list[dict], theme: dict
) -> dict[str, Any]:
    ans = _answer_lookup(transcript)
    title = (context.strip().split("\n")[0] or "Untitled Project")[:80]
    role = _find(ans, "role")
    problem = _find(ans, "problem") or context.strip()
    process = _find(ans, "process", "decision")
    outcome = _find(ans, "result", "outcome", "number")
    tools = _find(ans, "tool", "timeline", "platform")

    refs = [i["ref"] for i in image_meta]
    hero_ref = refs[0] if refs else None
    gallery = [
        {"ref": i["ref"], "caption": i.get("caption", "")}
        for i in image_meta[1:]
    ] or [{"ref": r, "caption": ""} for r in refs]

    blocks: list[dict] = [
        {"type": "hero", "title": title,
         "subtitle": (outcome or problem)[:140],
         "tags": [t for t in [role, tools] if t][:3], "image": hero_ref},
        {"type": "meta", "items": [
            {"label": "Role", "value": role or "Designer"},
            {"label": "Tools", "value": tools or "Figma"},
        ]},
        {"type": "text", "heading": "Overview",
         "body": context.strip() or problem},
        {"type": "text", "heading": "The Problem", "body": problem},
    ]
    if process:
        blocks.append({"type": "text", "heading": "Process", "body": process})
    blocks.append({
        "type": "flow-diagram", "heading": "User Flow",
        "mermaid": "flowchart TD\n  A[Entry] --> B[Browse]\n  B --> C[Detail]\n  C --> D[Action]\n  D --> E[Success]",
        "caption": "Core user flow.",
    })
    if gallery and gallery[0]["ref"]:
        blocks.append({"type": "gallery", "heading": "Designs", "images": gallery})
    if outcome:
        blocks.append({"type": "text", "heading": "Results & Impact", "body": outcome})

    return {
        "title": title,
        "summary": (outcome or problem)[:160],
        "recommended_template": "dark" if theme.get("mode") == "dark" else config.DEFAULT_TEMPLATE,
        "template_reason": "Chosen from the screens' overall light/dark feel.",
        "blocks": blocks,
        "engine": "fallback",
    }
