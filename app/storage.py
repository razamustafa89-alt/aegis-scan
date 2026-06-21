"""
Casefolio — SQLite persistence + image files.

One small table holds the whole lifecycle of a case study: the interview state
(context, Q&A transcript), the uploaded asset metadata, the generated block
document, and the chosen template + theme. JSON columns keep it simple for an MVP.

NOTE: the remote container is ephemeral, so this DB and the uploads dir do not
survive container recycling. Swap to Postgres + object storage for production.
"""

import json
import sqlite3
import time
import uuid
from typing import Any, Optional

from .config import DB_PATH, DEFAULT_TEMPLATE


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id            TEXT PRIMARY KEY,
                slug          TEXT UNIQUE,
                status        TEXT NOT NULL DEFAULT 'draft',
                context       TEXT NOT NULL DEFAULT '',
                transcript    TEXT NOT NULL DEFAULT '[]',
                assets        TEXT NOT NULL DEFAULT '[]',
                document      TEXT,
                template      TEXT NOT NULL DEFAULT '',
                theme         TEXT,
                created_at    INTEGER NOT NULL,
                updated_at    INTEGER NOT NULL
            )
            """
        )


def _now() -> int:
    return int(time.time() * 1000)


def _slugify(title: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    base = "-".join(p for p in base.split("-") if p)[:48] or "case"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for col in ("transcript", "assets", "document", "theme"):
        if d.get(col):
            try:
                d[col] = json.loads(d[col])
            except (TypeError, json.JSONDecodeError):
                d[col] = None
    return d


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------


def create_case(context: str) -> str:
    case_id = uuid.uuid4().hex
    now = _now()
    with _conn() as c:
        c.execute(
            "INSERT INTO cases (id, context, created_at, updated_at) VALUES (?,?,?,?)",
            (case_id, context, now, now),
        )
    return case_id


def get_case(case_id: str) -> Optional[dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_case_by_slug(slug: str) -> Optional[dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM cases WHERE slug=?", (slug,)).fetchone()
    return _row_to_dict(row) if row else None


def append_transcript(case_id: str, role: str, content: Any) -> None:
    case = get_case(case_id)
    if not case:
        return
    transcript = case.get("transcript") or []
    transcript.append({"role": role, "content": content})
    with _conn() as c:
        c.execute(
            "UPDATE cases SET transcript=?, updated_at=? WHERE id=?",
            (json.dumps(transcript), _now(), case_id),
        )


def add_asset(case_id: str, asset: dict[str, Any]) -> list[dict[str, Any]]:
    case = get_case(case_id)
    assets = (case.get("assets") if case else None) or []
    assets.append(asset)
    with _conn() as c:
        c.execute(
            "UPDATE cases SET assets=?, updated_at=? WHERE id=?",
            (json.dumps(assets), _now(), case_id),
        )
    return assets


def save_generated(case_id: str, document: dict[str, Any], template: str, theme: Optional[dict]) -> str:
    slug = _slugify(document.get("title", "case"))
    with _conn() as c:
        c.execute(
            """
            UPDATE cases
               SET document=?, template=?, theme=?, slug=?, status='published', updated_at=?
             WHERE id=?
            """,
            (json.dumps(document), template, json.dumps(theme) if theme else None, slug, _now(), case_id),
        )
    return slug


def update_presentation(case_id: str, template: Optional[str], theme: Optional[dict]) -> None:
    case = get_case(case_id)
    if not case:
        return
    new_template = template or case.get("template") or DEFAULT_TEMPLATE
    new_theme = theme if theme is not None else case.get("theme")
    with _conn() as c:
        c.execute(
            "UPDATE cases SET template=?, theme=?, updated_at=? WHERE id=?",
            (new_template, json.dumps(new_theme) if new_theme else None, _now(), case_id),
        )
