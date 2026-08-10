# CatalystEdge — Living Thesis Status

**Last updated:** 2026-08-09  
**Owner project:** `C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp`  
**GitHub intent:** fork/publish under `vikram17036` with attribution to original CatalystEdge authors  
**Local stack (current):** Frontend `http://localhost:3000` → API `http://127.0.0.1:8002`

---

## 1. Product vision (locked)

CatalystEdge is **Living Market Thesis Intelligence**, not a stock chatbot.

> People form market beliefs from changing evidence, but rarely have a system that tests those beliefs, records why they believed them, and tells them exactly when the evidence changes.

**Demo loop:**

```text
Analyze → Create / Propose Thesis → Freeze origin snapshot + evidence
       → Replay new evidence (fixture)
       → Same evaluator → Thesis Diff
       → Kill criteria → Alert on dashboard
```

**Permanent rules:**

1. Models interpret; tools calculate (no invented metrics / evidence IDs).
2. Replayability is first-class (demo must not wait for live crashes).
3. Deterministic kill criteria evaluated in code; qualitative kills need citations (later).
4. No `exec()` of LLM-generated Python (Strategy Lab later).

---

## 2. What we implemented

### Phase 0 — Foundation

| Piece | Path / notes | Status |
|--------|----------------|--------|
| Contracts | `stocksense/core/contracts.py` — Evidence, Claim, Thesis, ThesisDiff, Alert, KillCriterion | Done |
| Evidence ledger | `stocksense/core/evidence_ledger.py` — normalize price/news/fundamentals → Evidence[] | Done |
| Canonical pipeline | `stocksense/orchestration/pipeline.py` — wraps ReAct; returns `evidence_ledger` | Done |
| Alert unification | `stocksense/core/alerts_store.py` — prefer `thesis_alerts`, dual-write `alert_history` | Done |
| Migration | `supabase/migrations/005_living_thesis.sql` + `supabase/bootstrap_new_project.sql` | Done |
| Env / deploy notes | `.env.example`, `DEPLOY.md`, `frontend/vercel.json` | Done |
| Your Supabase | New project wired (URL + legacy anon JWT + service key) | Done |
| Keys | `GOOGLE_API_KEY` (Gemini), `NEWSAPI_KEY`, Supabase | Done |

### Phase 1 — Living Thesis DoD

| Piece | Path / notes | Status |
|--------|----------------|--------|
| Thesis Diff engine | `stocksense/core/thesis_diff.py` | Done |
| Thesis evaluate (single path) | `stocksense/core/thesis_evaluate.py` — live cache + fixtures | Done |
| Thesis propose/extract | `stocksense/core/thesis_extract.py` — structure from analysis (+ optional Gemini polish) | Done |
| Replay fixtures | `stocksense/core/replay_fixtures.py` + `tests/fixtures/replay/nvda_t0.json`, `nvda_t1.json` | Done |
| API: propose | `POST /api/theses/from-analysis` | Done |
| API: create thesis | `POST /api/theses` (with `origin_*` + `structured_kill_criteria`) | Done |
| API: compare | `GET /api/theses/{id}/compare` | Done |
| API: evaluate | `POST /api/theses/{id}/evaluate` | Done |
| API: replay | `POST /api/theses/{id}/replay` (`adverse_shock` / `nvda_t1`) | Done |
| API: alerts | `GET/PATCH /api/kill-alerts` → `thesis_alerts` (+ legacy fallback) | Done |
| Streaming evidence | `stocksense/orchestration/streaming.py` attaches `evidence_ledger` on complete | Done |
| UI: Header auth | `frontend/src/components/Header.tsx` + `UserMenu` | Done |
| UI: Living Thesis panel | `frontend/src/components/ThesisPanel.tsx` — propose/create, replay | Done |
| UI: Diff + Why | `frontend/src/components/ThesisDiffView.tsx` | Done |
| UI: Kill banner | Wired in `App.tsx` from `/api/kill-alerts` | Done |
| UI: Alerts center | `AlertsCenter.tsx` uses API (not only raw `alert_history`) | Done |
| Invariant tests | `tests/test_thesis_loop.py`, `tests/test_thesis_diff.py`, `tests/test_contracts.py` | Passing |

### Auth / env lessons learned

| Issue | Fix |
|--------|-----|
| Publishable key `sb_publishable_…` broke session | Use **Legacy anon JWT** (`eyJ…`) in `SUPABASE_ANON_KEY` / `VITE_SUPABASE_ANON_KEY` |
| Signup closed modal but stayed logged out | Email confirm on → disable for local, or confirm email; AuthModal now surfaces “needs confirm” |
| Google auth | Not configured; use email/password |
| Port clash with Fashion on `:8000` | CatalystEdge API moved off 8000; currently **`:8002`** |
| Uvicorn `--reload` hung on Windows | Prefer start **without** `--reload` when routes don’t update |

---

## 3. What is working (verified)

Use this as the regression checklist.

### Local run

- Frontend: `http://localhost:3000`
- Backend: `http://127.0.0.1:8002` (health/docs; `GET /api/phase1-ping` → `{ "phase1": true }`)
- Fashion Inspiration may still use `:8000` separately — do not share ports.

### User flows that work

1. **Sign in** (header top-right) with email/password against *your* Supabase → username shows (e.g. `SANDIGARU01`).
2. **Analyze NVDA** (Quick Access / Ctrl+K) → price hero, catalyst summary, risk signals, `SYS_ONLINE`.
3. **PROPOSE_AND_CREATE_THESIS** (or create from analysis) → thesis row in Supabase with origin snapshot / kill criteria.
4. **REPLAY_ADVERSE** → Diff (invalidated / weakened / kill) + optional **WHY** evidence.
5. **KILL_CRITERIA_TRIGGERED** banner appears (match conf, criteria text, ACK / VIEW_THESIS).
6. **SYS_ALERTS** (ADV menu / alerts view) lists thesis alerts via API.

### Tests

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
.\.venv\Scripts\python.exe -m pytest tests/test_thesis_loop.py tests/test_thesis_diff.py tests/test_contracts.py -q
```

Expect green (contracts + T0→T1 loop + reproducibility).

---

## 4. Known gaps / polish (still Phase 1-adjacent)

Not blockers for the demo, but incomplete:

| Gap | Notes |
|-----|--------|
| Analysis history `CACHE_EMPTY` | History UI can lag / not list Supabase cache consistently |
| Streaming vs POST analyze | Primary UX is SSE stream; kill check on stream path is still thinner than POST+auth |
| Qualitative kill criteria | Deterministic kills work; AI+citations qualitative path not fully built |
| Debate as hero | Still in codebase; demoted conceptually — Challenge under Diff later |
| Git remote | Local copy; not yet formally forked/pushed to `vikram17036` |
| Production deploy | Documented in `DEPLOY.md`; not live yet (Vercel FE + Render BE) |

---

## 5. What’s next (LOCKED order)

> **Do not change this roadmap.**  
> Immediate objective: **Turn the known-good local Phase 1 into a known-good live Phase 1.**

```text
Deploy → production smoke test → freeze Phase 1 → Event Study (Phase 2)
```

### Rule during deploy

- **Do not** refactor the thesis engine or add features.
- If Render/Vercel config is annoying, **do not destabilize the local demo** — local Phase 1 stays valuable; deploy is distribution.

### Step A — Deploy (in progress / next)

1. Push repo to GitHub (`vikram17036`) with attribution to original CatalystEdge authors.
2. **Vercel:** project root = `frontend`; env `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` → Render backend URL.
3. **Render:** use `render.yaml`; secrets = Google / NewsAPI / Supabase; `CORS_ORIGINS` = Vercel URL.
4. **Production smoke (exact regression — same as local):**

```text
login → analyze NVDA → create thesis → replay adverse fixture
     → Thesis Diff → WHY evidence → kill banner → alerts center
```

Fresh browser session on **public URLs**. If that passes → **deployment done; freeze Phase 1.**

### Step B — Phase 2 Event Study (only after freeze)

**Promise:**

> Ask CatalystEdge a historical market question and get a **reproducible quantitative experiment**, not an LLM opinion.

**Pipeline (narrow first cut):**

```text
Natural-language question
        ↓
EventStudySpec
        ↓
schema validation
        ↓
frozen event calendar + price data
        ↓
deterministic engine
        ↓
statistics + observations
        ↓
LLM interpretation (with citations to computed stats only)
        ↓
Evidence Ledger
```

**First demo follow-ups:**

1. “What happens to NVDA around FOMC decisions?”
2. “Only rate hikes.”
3. “Compare five days before with five days after.”

That transition: **living thesis product → AI-assisted research platform.**

### Phase 3+ (north star — do not start early)

| Phase | Theme |
|-------|--------|
| 3 | Strategy Lab — typed DSL, costs/slippage, no `exec()` |
| 4 | Attach experiments to theses |
| 5 | Historical Analog Search |
| 6 | Scenario Lab + Thesis Dependency Graph |
| 7 | Research Memory + Postmortems |
| 8 | Deep eval corpus + observability + hardening |

Eventual nav: `RESEARCH · LAB · THESES · MONITOR · MEMORY` (not “Bull Agent”).

---

## 6. How to start locally (cheat sheet)

```powershell
# Backend (no --reload preferred on Windows)
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
.\.venv\Scripts\uvicorn.exe stocksense.main:app --host 127.0.0.1 --port 8002

# Frontend (separate terminal)
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp\frontend
# ensure frontend/.env.local has VITE_API_URL=http://127.0.0.1:8002
npm run dev
```

**Env files:**

- Root `.env` — `GOOGLE_API_KEY`, `NEWSAPI_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (JWT), `SUPABASE_SERVICE_KEY`
- `frontend/.env.local` — `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (same JWT), `VITE_API_URL`

**Supabase:** run `supabase/bootstrap_new_project.sql` once on a new project; Auth → Email → confirm email off for local.

---

## 7. Portfolio context

| Project | Role |
|---------|------|
| **CatalystEdge** | Flagship — living thesis + (later) experiments |
| **Fashion Atelier** | Multimodal / Compose grounding |
| **Receipts** | Product judgment + human-approved AI |
| Wardrobe try-on | Backlog — not started |

---

## 8. Change log (session summary)

1. Adopted CatalystEdge as Living Thesis flagship; Phase 0 contracts + pipeline + alerts schema.
2. Replaced friend’s keys with Vikram’s Supabase + Gemini + NewsAPI.
3. Fixed port conflicts (Fashion `:8000`) and auth (legacy JWT anon key).
4. Shipped Phase 1: propose/create thesis, replay fixtures, Diff/Why UI, kill alerts banner.
5. Verified end-to-end kill alert on NVDA adverse replay.
6. API stabilized on **`:8002`** after Windows reload hang on `:8001`.

---

*Maintain this file as the source of truth for “what’s done / what’s next.” Update the date and checklists when a phase completes or deploy goes live.*
