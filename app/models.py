"""
Casefolio — request models and the structured JSON schemas.

The block schema here is the single source of truth: it is handed to Claude as
a tool `input_schema` (so generation is always valid JSON we can render) and is
also what the frontend renders block-by-block.
"""

from typing import Any, Optional

from pydantic import BaseModel

# ----------------------------------------------------------------------
# API request bodies
# ----------------------------------------------------------------------


class CreateCaseRequest(BaseModel):
    context: str


class AnswersRequest(BaseModel):
    # Map of question text -> answer text. Free-form so the wizard can post
    # whatever questions the model asked.
    answers: dict[str, str]


class PatchCaseRequest(BaseModel):
    template: Optional[str] = None
    theme: Optional[dict[str, Any]] = None


class ExternalProject(BaseModel):
    title: str
    url: str
    thumbnail: Optional[str] = ""
    blurb: Optional[str] = ""


class CreatePortfolioRequest(BaseModel):
    context: str
    case_slugs: list[str] = []
    external: list[ExternalProject] = []


class ContactRequest(BaseModel):
    name: str = ""
    email: str = ""
    body: str


# ----------------------------------------------------------------------
# Tool schemas given to Claude
# ----------------------------------------------------------------------

# 1) Adaptive interview — the model returns the next batch of questions.
QUESTIONS_TOOL = {
    "name": "ask_followups",
    "description": (
        "Return the next round of focused follow-up questions for the designer, "
        "or signal that enough information has been gathered."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ready": {
                "type": "boolean",
                "description": "True when there is enough to write a strong case study.",
            },
            "questions": {
                "type": "array",
                "description": "0-6 short, specific questions that fill gaps in the case-study structure.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Short stable id, e.g. 'role'."},
                        "question": {"type": "string"},
                        "why": {
                            "type": "string",
                            "description": "One short line on why this matters (shown as a hint).",
                        },
                        "placeholder": {"type": "string", "description": "Example answer."},
                    },
                    "required": ["id", "question"],
                },
            },
        },
        "required": ["ready", "questions"],
    },
}

# 2) Vision pass — per-image caption + section, plus an extracted brand palette.
VISION_TOOL = {
    "name": "describe_screens",
    "description": (
        "Describe each uploaded UI screen and extract the product's brand palette "
        "so the case study can be themed on-brand."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "The asset ref provided for this image."},
                        "caption": {
                            "type": "string",
                            "description": "A decision-focused caption (what the screen does / why it matters).",
                        },
                        "suggested_section": {
                            "type": "string",
                            "enum": ["hero", "process", "solution", "research", "other"],
                        },
                    },
                    "required": ["ref", "caption", "suggested_section"],
                },
            },
            "theme": {
                "type": "object",
                "description": "Brand palette derived from the screens (hex colors).",
                "properties": {
                    "primary": {"type": "string", "description": "Dominant brand color, hex."},
                    "accent": {"type": "string", "description": "Secondary/accent color, hex."},
                    "bg": {"type": "string", "description": "Page background, hex."},
                    "surface": {"type": "string", "description": "Card/surface color, hex."},
                    "text": {"type": "string", "description": "Primary text color, hex."},
                    "mode": {"type": "string", "enum": ["light", "dark"]},
                },
                "required": ["primary", "accent", "bg", "surface", "text", "mode"],
            },
        },
        "required": ["images", "theme"],
    },
}

# 3) Generation — the full case study as ordered, typed blocks.
_BLOCK = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["hero", "meta", "text", "gallery", "flow-diagram", "chart", "quote", "metrics"],
        },
        # hero / text / generic
        "heading": {"type": "string"},
        "title": {"type": "string"},
        "subtitle": {"type": "string", "description": "Hero: one-line impact statement."},
        "body": {"type": "string", "description": "Paragraph copy. Plain text; blank line separates paragraphs."},
        "tags": {"type": "array", "items": {"type": "string"}},
        "image": {"type": "string", "description": "Asset ref for a single image (hero)."},
        # meta / metrics
        "items": {
            "type": "array",
            "description": "meta: {label,value} pairs. metrics: {value,label} stat pairs.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        },
        # gallery
        "images": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Asset ref of an uploaded screen."},
                    "caption": {"type": "string"},
                },
                "required": ["ref"],
            },
        },
        # flow-diagram
        "mermaid": {"type": "string", "description": "Valid Mermaid source (flowchart TD ...)."},
        "caption": {"type": "string"},
        # chart
        "chart_type": {"type": "string", "enum": ["bar", "line", "doughnut"]},
        "labels": {"type": "array", "items": {"type": "string"}},
        "datasets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "data": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["data"],
            },
        },
        # quote
        "text": {"type": "string"},
        "attribution": {"type": "string"},
    },
    "required": ["type"],
}

CASE_TOOL = {
    "name": "build_case_study",
    "description": "Produce the complete, publication-ready designer case study as ordered blocks.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string", "description": "1-2 sentence TL;DR used for sharing previews."},
            "recommended_template": {
                "type": "string",
                "enum": ["editorial", "bold", "minimal", "dark"],
            },
            "template_reason": {"type": "string", "description": "One line on why this template fits."},
            "blocks": {"type": "array", "items": _BLOCK},
        },
        "required": ["title", "summary", "recommended_template", "blocks"],
    },
}


# 4) Portfolio generation — a personal site as ordered blocks.
_PORTFOLIO_BLOCK = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["intro", "about", "work", "skills", "testimonials", "contact"],
        },
        # intro
        "name": {"type": "string"},
        "role": {"type": "string", "description": "Headline role, e.g. 'Product Designer'."},
        "tagline": {"type": "string"},
        "avatar": {"type": "string", "description": "Asset ref for the avatar image."},
        "location": {"type": "string"},
        "links": {
            "type": "array",
            "description": "Social/contact links.",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "url": {"type": "string"}},
                "required": ["label", "url"],
            },
        },
        # about / generic
        "heading": {"type": "string"},
        "body": {"type": "string"},
        # work
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "blurb": {"type": "string"},
                    "thumbnail": {"type": "string", "description": "Image URL (provided in the prompt)."},
                    "href": {"type": "string", "description": "Link to the case study or external project."},
                },
                "required": ["title"],
            },
        },
        # skills
        "skills": {"type": "array", "items": {"type": "string"}},
        # testimonials
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "attribution": {"type": "string"}},
                "required": ["text"],
            },
        },
        # contact
        "email": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["type"],
}

PORTFOLIO_TOOL = {
    "name": "build_portfolio",
    "description": "Produce a complete, publication-ready designer portfolio site as ordered blocks.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Usually the designer's name."},
            "summary": {"type": "string", "description": "1-2 sentence description for sharing previews."},
            "recommended_template": {
                "type": "string",
                "enum": ["editorial", "bold", "minimal", "dark"],
            },
            "template_reason": {"type": "string"},
            "blocks": {"type": "array", "items": _PORTFOLIO_BLOCK},
        },
        "required": ["title", "summary", "recommended_template", "blocks"],
    },
}
