# AIMark — Brand Brain

AI marketing-content tool built around a **Brand Brain**: a setup phase that captures a
brand's strategy, audience, voice, and competitive intel once, then feeds an AI
generation engine on every content request.

Built **phase by phase**, mirroring the 6 setup stages from the spec:

| Phase | Stage | Status |
|-------|-------|--------|
| 1 | Brand inputs (vision, goal, moat) | ✅ Done |
| 2 | ICP builder (personas + variants) | ✅ Done |
| 3 | Competitors — context, regions, fetch, analysis | ✅ Done |
| 4 | Content creation | ⏳ Next |

_(A Voice codifier stage existed but was removed.)_

## Stack

- **Backend:** FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL 16 · managed with `uv`
- **Frontend:** React + TypeScript + Vite
- **DB:** Postgres (`aimark` db / `aimark` role)

## Layout

```
AIMark/
├── backend/
│   ├── app/
│   │   ├── api/        # routers (brands.py)
│   │   ├── core/       # config/settings
│   │   ├── db/         # engine, session, declarative base
│   │   ├── models/     # SQLAlchemy models (Brand)
│   │   ├── schemas/    # Pydantic schemas
│   │   └── main.py     # FastAPI app
│   └── alembic/        # migrations
└── frontend/
    └── src/
        ├── components/ # BrandInputs.tsx
        ├── api.ts      # typed API client
        ├── phases.ts   # 6-phase model
        └── App.tsx     # phase navigator shell
```

## Running locally

Prereqs: Postgres running with an `aimark` database/role (see below), `uv`, Node 18+.

```bash
# one-time DB setup (if not already done)
createdb aimark            # or via the CREATE ROLE/DATABASE statements

# backend  (http://localhost:8000, docs at /docs)
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# frontend (http://localhost:5173, proxies /api → :8000)
cd frontend
npm install
npm run dev
```

## Phase 1 API

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/brands`        | list brands |
| POST   | `/api/brands`        | create brand |
| GET    | `/api/brands/{id}`   | fetch one |
| PATCH  | `/api/brands/{id}`   | partial update |
| DELETE | `/api/brands/{id}`   | delete |

`Brand` = `{ name, vision, goal, moat }` (+ id, timestamps). `name` required; the
rest optional and trimmed. Each later phase adds related tables keyed on `brand.id`.

## Phase 2 API (ICP builder)

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/brands/{brand_id}/personas` | list personas (variants nested) |
| POST   | `/api/brands/{brand_id}/personas` | create persona (max 5/brand → 400) |
| PATCH  | `/api/personas/{id}`              | update; sending `variants` replaces the list |
| DELETE | `/api/personas/{id}`              | delete (variants cascade) |

`Persona` = `{ name, user_type, business_size, region, pain_points,
current_platforms, main_goal, variants: [{ label, description }] }` keyed on a
brand. `user_type` (Accountant/CA/Business owner) and `business_size` (Small/SME)
are dropdowns; the rest free text. Max 5 personas per brand; each holds any number
of variants. Front-end phases are switched via the top tab strip in `App.tsx`.

## Competitors API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/brands/{id}/context` | aggregate context from earlier stages: `{ brand, personas }` |
| GET | `/api/brands/{id}/competitor-scope` | operating regions (auto-creates empty) |
| PUT | `/api/brands/{id}/competitor-scope` | save regions |

The Competitors stage starts by selecting a brand, then **pulls that brand's
context** (vision/goal/moat, personas) into a read-only panel, and asks for
the operating `regions` (a deduped string list on `CompetitorScope`, one row per
brand). Regions seed competitor discovery.

**Fetch competitors (LLM):**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/brands/{id}/competitors` | list fetched competitors |
| POST | `/api/brands/{id}/competitors/fetch` | LLM generates competitors from stage 1–2 context + regions, saved as `pending` |
| PATCH | `/api/competitors/{id}` | tick/cross → `considered` / `rejected` |
| DELETE | `/api/competitors/{id}` | remove |

`Competitor` = `{ name, website, description, status: pending/considered/rejected, is_primary }`.
`POST /competitors/{id}/pick` marks one considered competitor as the primary
(clears any prior pick for the brand); the UI shows it below the shortlist.
`POST /competitors/{id}/analyze` runs an LLM analysis (stored in `analysis` JSONB):
name, revenue, users, top-5 moats, social presence (instagram/blog/facebook/x
booleans + thirdparty name), and features-marketed each with a sample-marketing
line. **Revenue and users are looked up via OpenAI web search** (Responses API,
`web_search` tool) from reputable sources, and each records a `revenue_source` /
`users_source` citation (shown as a link in the UI). Moats/social/features come
from model knowledge. "NA" only when a figure genuinely can't be found. Auto-runs
when a competitor is picked; rendered as tables in the UI.
The LLM call is isolated in `app/services/llm.py` (OpenAI, model via `OPENAI_MODEL`,
key via `OPENAI_API_KEY` in `.env`) — swapping providers is a one-file change.
Structured JSON-schema output guarantees a typed competitor list.

## Adding a phase

1. Backend: add model in `app/models/`, register in `app/models/__init__.py`,
   `alembic revision --autogenerate`, `alembic upgrade head`, add schemas + router.
2. Frontend: add a component, flip its entry in `src/phases.ts` from `upcoming` to
   `active`, wire it into `App.tsx`.
