# CatalystEdge — Deploy + Keys

## Keys (yours, not the friend's)

This backend uses **Google Gemini**, not OpenAI.

| Variable | Where | Notes |
|----------|--------|--------|
| `GOOGLE_API_KEY` | root `.env` | https://aistudio.google.com/app/apikey |
| `NEWSAPI_KEY` | root `.env` | https://newsapi.org/register |
| `SUPABASE_URL` | root `.env` + `frontend/.env` | Your project URL |
| `SUPABASE_ANON_KEY` | root `.env` + `frontend/.env` as `VITE_SUPABASE_ANON_KEY` | Public anon key |
| `SUPABASE_SERVICE_KEY` | root `.env` only | Service role — never commit / never put in Vite |
| `VITE_API_URL` | `frontend/.env` | Production: your Render backend URL |

Optional: Fashion uses `OPENAI_API_KEY`. CatalystEdge does **not** read it today.

### Local setup

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
copy .env.example .env
# edit .env with YOUR keys

cd frontend
copy ..\.env.example .env.local
# keep only VITE_* lines in frontend/.env.local and set VITE_API_URL=http://127.0.0.1:8000
```

In Supabase SQL editor (your project), run migrations in order under `supabase/`, including:

`supabase/migrations/005_living_thesis.sql`

### Deploy architecture

| Piece | Host | Why |
|-------|------|-----|
| React frontend | **Vercel** | Static Vite build |
| FastAPI + scheduler | **Render** (see `render.yaml`) | Long-running API + Watchman job; not a fit for Vercel serverless as-is |

### Frontend → Vercel

1. Push this repo to GitHub (`vikram17036`).
2. Vercel → New Project → root directory = `frontend`.
3. Env vars in Vercel:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `VITE_API_URL` = `https://<your-render-service>.onrender.com`
4. Deploy.

### Backend → Render

1. New Web Service from `render.yaml`, or Blueprint.
2. Set the same secrets as `.env` (Google, NewsAPI, Supabase).
3. Set `CORS_ORIGINS` to your Vercel URL (comma-separated if multiple).

### Smoke check after deploy (exact Phase 1 regression)

Fresh browser session on **public** URLs only:

```text
login → analyze NVDA → create thesis → replay adverse fixture
     → Thesis Diff → WHY evidence → kill banner → alerts center
```

If that passes, deployment is done and Phase 1 is frozen. Do not refactor the thesis engine to “fix” hosting issues — keep the local demo intact.

### Rule

Deploy is distribution. If Render/Vercel config is painful, stop and leave local Phase 1 alone rather than rewriting working code.
