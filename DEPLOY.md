# CatalystEdge — Deploy + Keys

## Keys (yours, not the friend's)

This backend uses **Google Gemini**, not OpenAI.

| Variable | Where | Notes |
|----------|--------|--------|
| `GOOGLE_API_KEY` | root `.env` | https://aistudio.google.com/app/apikey |
| `NEWSAPI_KEY` | root `.env` | https://newsapi.org/register |
| `SUPABASE_URL` | root `.env` + `frontend/.env.local` | Your project URL |
| `SUPABASE_ANON_KEY` | root `.env` + `frontend/.env.local` as `VITE_SUPABASE_ANON_KEY` | Public anon key |
| `SUPABASE_SERVICE_KEY` | root `.env` only | Service role — never commit / never put in Vite |
| `PINECONE_API_KEY` | root `.env` + Render | https://app.pinecone.io |
| `PINECONE_INDEX` | root `.env` + Render | Custom dense index: **768 dims, cosine** |
| `VITE_API_URL` | `frontend/.env.local` | Local `http://127.0.0.1:8002`; prod = Render URL |

Pinned backend extras (Render installs `requirements-backend.txt`): `pinecone==9.1.0`, `google-genai==2.17.0`.

### Local setup

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
copy .env.example .env
# edit .env with YOUR keys (incl. PINECONE_*)

cd frontend
# VITE_* in frontend/.env.local ; VITE_API_URL=http://127.0.0.1:8002
```

In Supabase SQL editor, run migrations `001`–`010` (or `bootstrap_new_project.sql` for greenfield).

### Deploy architecture

| Piece | Host | Why |
|-------|------|-----|
| React frontend | **Vercel** | Static Vite build |
| FastAPI + scheduler | **Render** (see `render.yaml`) | Long-running API; not Vercel serverless |

### Backend → Render

1. Connect `vikram17036/catalystedge-living-thesis` (Blueprint or existing `catalystedge-backend`).
2. Set secrets:
   - `GOOGLE_API_KEY`, `NEWSAPI_KEY`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
   - `PINECONE_API_KEY`, `PINECONE_INDEX`
   - `CORS_ORIGINS` = Vercel origin (not `*` in prod)
3. **Manual Redeploy** after push (avoid stale OpenAPI).
4. Confirm `GET /api/research-agent-ping` and `GET /api/ready` on the Render URL.

**Note:** LangGraph conversation memory (`InMemorySaver`) is process-local — cold starts reset threads. Durable research remains in Supabase/Pinecone.

### Frontend → Vercel

1. Root Directory = `frontend`.
2. Env: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` = Render URL (no trailing slash).
3. Redeploy after backend URL/env changes.

### Supabase Auth

Site URL + Redirect URLs must include the Vercel origin and `http://localhost:3002/**` (or your local port).

### Smoke check after deploy (P1–P8)

Fresh browser on **public** URLs:

```text
login → analyze NVDA → create thesis → attach research
     → analogs → scenario WHAT-IF
     → AGENT hero → Follow-up −12% (writes=0)
     → GET /health (cheap flags) → GET /api/ready (deps; pinecone optional degrade)
```

### Regression (local)

```powershell
.\scripts\regression.ps1
```

### Rule

Deploy is distribution. After Phase 8, stop adding product phases — polish demo, narrative, and keep the prod walkthrough boringly reliable.
