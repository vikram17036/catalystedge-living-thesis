# CatalystEdge — STATUS (single source of truth)

**Last updated:** 2026-08-10  
**Repo:** https://github.com/vikram17036/catalystedge-living-thesis  
**Local:** UI `localhost:3002` (or 3000) → API `127.0.0.1:8002`  
**Prod:** https://catalystedge-living-thesis-pearl.vercel.app · https://catalystedge-backend.onrender.com  

**Rule:** Keep **done** and **next** in this document only. Do not spawn separate phase plan files.

---

## Product (locked)

1. Models interpret; tools calculate.  
2. Replayability first-class.  
3. Deterministic kills/stats in code.  
4. No `exec()` of LLM Python.  
5. **`origin_evidence` is frozen at thesis create** — later research never rewrites it.

**Architecture:** LangGraph orchestrates · RAG remembers · deterministic engines calculate · evidence validates

**Progression:** P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 · **stop adding product phases**

**Three memories:**
1. **Working** — LangGraph `InMemorySaver` + `user_id:thread_id` (process-local; lost on restart)
2. **Structured** — Supabase (authoritative)
3. **Semantic** — Pinecone refs → Supabase hydrate (auth via ContextVar, never checkpointed)

---

# DONE SO FAR

## Phase 1–7 — as before (P7 agent + Pinecone VERIFIED locally)

## Phase 8 — Eval, Observability, Deploy-ready — IMPLEMENTED locally

- `research_trace_v1` execution receipt (tool split, engine_repro, sanitized errors, timings)
- User-namespaced checkpoint threads; JWT not in graph state
- Eval corpus + scorecard: `tests/test_research_agent_eval.py`
- `/health` cheap (no network); `/api/ready` TTL-cached deps (Pinecone optional degrade)
- `X-Request-Id` + latency logging
- AGENT UI = research plan receipt + reindex counts
- Deploy unblock: `pinecone==9.1.0`, `google-genai==2.17.0` in `requirements-backend.txt`; `PINECONE_*` in `render.yaml`; `DEPLOY.md` P8 smoke

### Regression

```powershell
.\scripts\regression.ps1
```

### Prod ship (manual once)

1. Push + Render Redeploy  
2. Set `PINECONE_API_KEY`, `PINECONE_INDEX`, `CORS_ORIGINS` on Render  
3. Smoke: login → thesis → labs → AGENT hero → −12% → `/api/ready`

---

# NEXT

**No P9 product phase.** Maintain / demo polish / interview narrative / keep prod walkthrough reliable.

**UI:** Shell + content presentation frozen for demo (2026-08-09). Do not redesign; only fix breakages.

**Prod ship:** Push → Render Manual Redeploy → confirm `/api/research-agent-ping` + `/api/ready` → Vercel auto (frontend).

---

## Local cheat sheet

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
.\.venv\Scripts\uvicorn.exe stocksense.main:app --host 127.0.0.1 --port 8002
cd frontend
npm run dev
.\scripts\regression.ps1
```

---

## Change log

1. P1–P7 as above.  
2. Phase 8: measure agent, expose receipt, harden health/deps, pin deploy deps.  
3. Demo UI polish: grey hierarchy, human evidence cards, Agent loading, chip fill-only.  
4. Start-new thesis: close preserves dependents; `/api/theses/start-new` is one fast Supabase round-trip; Pinecone index deferred via BackgroundTasks (does not block UI).  
5. Agent routing: NL phrases for SMA/FOMC/historical momentum now select Strategy Lab, Event Study, and Analogs (plus Scenario); engines still calculate; LLM only synthesizes.  
6. Agent synthesis: pass compact MEASURED_LAB_RESULTS (event means/rates, etc.) instead of truncating full observation tables mid-JSON.  
7. Thesis assessment pack: “still make sense / reconsider” auto-selects market regime + analogs + scenario + FOMC event study + strategy lab; new `get_market_regime` tool (SMA20/50/200 state); synthesis requires partial-failure honesty; yfinance price fetch TTL-cached.  
8. Start-new thesis UI: review editor shows analysis confidence and lets user customize before close+create.  

*Maintain only this file for what’s done / what’s next.*
