# Casefolio — AI Case Study Generator for Designers

Designers struggle to turn their work into compelling **case studies** that win
clients and jobs. Dribbble shots and raw Figma links don't tell the strategic
story. Casefolio fixes that: it **interviews** the designer, lets them **upload
their real screens**, then **generates a polished, shareable case-study web page** —
with AI-written narrative, auto-built **user-flow / IA diagrams**, **results charts**,
and a layout **themed to the product's brand**.

> This repo previously hosted *AegisScan* (a URL security scanner). That project is
> preserved under [`legacy/`](legacy/) for reference and is not used by Casefolio.

## How it works

1. **Smart interview** — paste your project context; the AI asks only the
   follow-up questions that surface your role, decisions, and impact.
2. **Upload screens** — drop in your real designs. They're captioned and placed in
   the right sections, and their colors are extracted to theme the page.
3. **Generate** — get the narrative, Mermaid flow/IA diagrams, and results charts as
   one structured document.
4. **Pick a template** — choose from multiple layouts (`editorial`, `bold`,
   `minimal`, `dark`); the best fit is **recommended**. Switch anytime and tweak the
   brand colors. Share the live `/case/{slug}` link.

## Architecture

- **Backend:** FastAPI (`app/`). The case-study lifecycle lives in `app/main.py`;
  Claude integration (interview, vision captioning + palette, generation) in
  `app/ai.py`; the structured block schema (also the Claude tool schema) in
  `app/models.py`; persistence (SQLite + uploaded files) in `app/storage.py`.
- **Frontend:** zero-build vanilla JS (`web/`). The public page renders a
  **block document** (`hero`, `meta`, `text`, `gallery`, `flow-diagram`, `chart`,
  `quote`, `metrics`) and applies the selected template + brand theme. Diagrams via
  Mermaid, charts via Chart.js (both from CDN).
- **AI:** the official `anthropic` SDK with **tool-forced** structured output, so
  generation is always valid JSON. Default model `claude-sonnet-4-6` (vision-capable).
  Without an API key, Casefolio runs a built-in **offline fallback** so the full flow
  still works for demos.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env        # set ANTHROPIC_API_KEY for live AI (optional for demo)
uvicorn app.main:app --reload
# open http://localhost:8000  → "Start a case study"
```

API: `POST /api/case-studies` → `POST .../answers` → `POST .../assets` →
`POST .../generate` → page at `/case/{slug}`. `PATCH /api/case-studies/{id}` updates
the template/theme. `GET /api/health` reports whether AI is live.

## Portfolio builder (phase 2)

Designers can also generate a full **portfolio website**. The flow mirrors the
case-study builder and reuses the same templates + brand theming:

1. Add a short bio → **pick which case studies to feature** (from your published
   ones) and **add external project links** (Dribbble/Behance/live sites).
2. Optionally upload an avatar, then answer a few follow-up questions.
3. Generate → a shareable site at `/p/{slug}` with intro, about, a work grid
   (case-study cards + external links), skills, testimonials, and a **contact form**.

The contact form works with **zero setup**: submissions persist server-side
(`GET /api/portfolios/{id}/messages`) and are additionally emailed if the optional
`SMTP_*` env vars are configured. Start it from the landing page → "Build my portfolio",
or go to `/portfolio`.

Portfolio API: `GET /api/case-studies` (work picker) · `POST /api/portfolios` →
`POST .../answers` → `POST .../assets` → `POST .../generate` → page at `/p/{slug}` ·
`PATCH /api/portfolios/{id}` (template/theme) · `POST /api/portfolio/{slug}/contact`.

## Notes & limitations

- Storage is SQLite + a local `uploads/` dir — **ephemeral** on managed/remote
  containers. Move to Postgres + object storage (S3) for production durability.
- Live generation calls `api.anthropic.com`; the environment's network policy must
  allow outbound access to Anthropic.
- **Roadmap:** designer accounts (so the work picker is scoped per user), inline
  editing of generated copy, custom domains, and durable cloud storage.
