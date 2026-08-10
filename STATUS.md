# CatalystEdge — STATUS (single source of truth)

**Last updated:** 2026-08-09  
**Repo:** https://github.com/vikram17036/catalystedge-living-thesis  
**Local:** UI `localhost:3002` (or 3000) → API `127.0.0.1:8002`  
**Prod:** https://catalystedge-living-thesis-pearl.vercel.app · https://catalystedge-backend.onrender.com  
*(Phase 2–4 code on GitHub; full prod redeploy deferred)*

**Rule:** Keep **done** and **next** in this document only. Do not spawn separate phase plan files.

---

## Product (locked)

1. Models interpret; tools calculate.  
2. Replayability first-class.  
3. Deterministic kills/stats in code.  
4. No `exec()` of LLM Python.  
5. **`origin_evidence` is frozen at thesis create** — later research never rewrites it.

**Progression:** P1 belief → P2 historical test → P3 safe rule sim → P4 attach research without rewriting origin

---

# DONE SO FAR

## Phase 1 — Living Thesis — FROZEN (prod smoke)

Analyze → thesis → origin freeze → replay → Diff/Why → kill → alerts.

## Phase 2 — Event Study — FROZEN locally

RESEARCH: NVDA FOMC → hikes → ±5d. Pure engine + `fomc_v1`.

## Phase 3 — Strategy Lab — locally verified

LAB: 20/50 SMA NVDA → costs → show DD/hit rate (no spec mutation).

## Phase 4 — Attach Experiments — IMPLEMENTED

**Storage:** `thesis_evidence` table (`006_thesis_evidence.sql`) — **not** `origin_evidence`.

**API:** `POST /api/theses/attach-by-ticker`, `POST /api/theses/{id}/attach-evidence`

**UI:** ATTACH_TO_THESIS on RESEARCH + LAB; ATTACHED_EXPERIMENTS on ThesisPanel; WHY = ORIGIN | ATTACHED | CURRENT (Diff math still origin vs current only).

**Required in Supabase SQL editor:** `006_thesis_evidence.sql`, then **`007_thesis_evidence_grants.sql`** (grants/RLS — without this, attach can look successful but nothing persists).

### Hero demo

```text
Create NVDA thesis → origin frozen
RESEARCH → ATTACH_TO_THESIS
LAB → ATTACH_TO_THESIS
ThesisPanel → ATTACHED_EXPERIMENTS
Replay → Diff still uses original baseline; WHY shows three sections
```

### Regression

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thesis_attach.py tests/test_thesis_loop.py tests/test_event_study.py tests/test_strategy_lab.py tests/test_contracts.py -q
```

---

# NEXT

**Deploy status (2026-08-09):**
- Pushed `2b6b2ae` to `main` (Phase 4 attach fixes + `007` grants).
- **Vercel frontend:** Production deploy for `2b6b2ae` succeeded → https://catalystedge-living-thesis-pearl.vercel.app
- **Render backend:** still serving Phase‑1 OpenAPI (no `/attach-by-ticker`, research, lab). **Manual Redeploy** required in Render for `catalystedge-backend` (auto-deploy may be off / stale).
- **Prod Supabase:** run `006_thesis_evidence.sql` + `007_thesis_evidence_grants.sql` in the **production** project SQL editor (if not already).

Then Phase 5+ only when intentional:

| Phase | Theme |
|-------|--------|
| 5 | Historical Analog Search |
| 6 | Scenario Lab + Thesis Dependency Graph |
| 7 | Research Memory + Postmortems |
| 8 | Deep eval + observability |

---

## Local cheat sheet

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
.\.venv\Scripts\uvicorn.exe stocksense.main:app --host 127.0.0.1 --port 8002
cd frontend
npm run dev
```

---

## Change log

1. P1–P3 as above.  
2. Phase 4: `thesis_evidence` + attach APIs + UI; origin/Diff untouched.  
3. Phase 4 fix: fail hard on empty insert, grants migration `007`, cache invalidate, always show ATTACHED_EXPERIMENTS count.  

*Maintain only this file for what’s done / what’s next.*
