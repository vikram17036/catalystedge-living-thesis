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

### Backend → Render

**One-click Blueprint** (after repo is on GitHub):

https://dashboard.render.com/blueprint/new?repo=https%3A%2F%2Fgithub.com%2Fvikram17036%2Fcatalystedge-living-thesis

1. Connect the `vikram17036/catalystedge-living-thesis` repo (or open the link above).
2. Service name should be `catalystedge-backend` from `render.yaml`.
3. Set secrets (same as root `.env`):
   - `GOOGLE_API_KEY`, `NEWSAPI_KEY`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY` (Legacy JWT), `SUPABASE_SERVICE_KEY`
   - `CORS_ORIGINS` — leave `*` until Vercel URL exists, then set to the Vercel origin
4. Deploy → copy the public URL (e.g. `https://catalystedge-backend.onrender.com`).

Free-tier note: no persistent disk in `render.yaml` (ephemeral `/tmp` cache only). Cold starts are OK for smoke; do not rewrite the app to chase free-tier quirks.

### Frontend → Vercel

1. Vercel → New Project → import `vikram17036/catalystedge-living-thesis`.
2. **Root Directory** = `frontend` (required).
3. Env vars:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY` (same Legacy JWT anon key)
   - `VITE_API_URL` = Render backend URL from above (**no trailing slash**)
4. Deploy.

### Supabase Auth (required for live login)

In your Supabase project → Authentication → URL configuration:

- **Site URL** = your Vercel URL
- **Redirect URLs** include `https://<vercel-app>.vercel.app/**` and `http://localhost:3000/**`

Without this, production login fails even if the API is healthy.
### Smoke check after deploy (exact Phase 1 regression)

Fresh browser session on **public** URLs only:

```text
login → analyze NVDA → create thesis → replay adverse fixture
     → Thesis Diff → WHY evidence → kill banner → alerts center
```

If that passes, deployment is done and Phase 1 is frozen. Do not refactor the thesis engine to “fix” hosting issues — keep the local demo intact.

### Rule

Deploy is distribution. If Render/Vercel config is painful, stop and leave local Phase 1 alone rather than rewriting working code.
