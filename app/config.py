"""
Casefolio — runtime configuration.

All knobs come from environment variables (see .env.example). Nothing here
imports the rest of the app, so it is safe to import from anywhere.
"""

import os
from pathlib import Path

# Load a local .env if python-dotenv is available (optional dependency).
try:  # pragma: no cover - convenience only
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = Path(os.environ.get("CASEFOLIO_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("CASEFOLIO_UPLOAD_DIR", BASE_DIR / "uploads"))
DB_PATH = DATA_DIR / "casefolio.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# AI
# ----------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Default to a capable, vision-enabled, cost-effective model.
MODEL = os.environ.get("CASEFOLIO_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("CASEFOLIO_MAX_TOKENS", "8000"))

# ----------------------------------------------------------------------
# Uploads
# ----------------------------------------------------------------------
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_UPLOAD_BYTES = int(os.environ.get("CASEFOLIO_MAX_UPLOAD_MB", "8")) * 1024 * 1024
MAX_IMAGES_PER_CASE = 20

# Templates the renderer supports. The first one is the safe default.
TEMPLATES = ["editorial", "bold", "minimal", "dark"]
DEFAULT_TEMPLATE = "editorial"


# ----------------------------------------------------------------------
# Contact form email (all optional). Without these, submissions are still
# stored server-side; they are only emailed when SMTP is configured.
# ----------------------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_TO = os.environ.get("SMTP_TO", "")


def ai_enabled() -> bool:
    """True when a key is configured and the SDK can be used."""
    return bool(ANTHROPIC_API_KEY)


def smtp_enabled() -> bool:
    return bool(SMTP_HOST and SMTP_TO)
