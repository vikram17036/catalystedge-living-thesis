# CatalystEdge AI

CatalystEdge AI is a full-stack stock research app that explains why a stock may be moving.

It collects recent financial news, historical price data, and company fundamentals, then uses Google Gemini with a ReAct-style workflow to generate a structured analysis. Results are streamed to the React frontend in real time and saved in Supabase.

## Features

- Search by company name or ticker
- Real-time AI analysis with SSE streaming
- Historical prices and fundamentals from yfinance
- Recent financial news from NewsAPI
- Sentiment, confidence, key themes, risks, and skeptic analysis
- Price movement compared with the previous close
- Clickable article sources and numbered citations
- Analysis history stored in Supabase
- Advanced pages for authentication, theses, kill criteria, and alerts

## Tech Stack

- React, TypeScript, Vite, Tailwind CSS
- Python, FastAPI, LangChain, LangGraph
- Google Gemini
- Supabase PostgreSQL
- NewsAPI
- yfinance

## How It Works

1. The user searches for a company or ticker.
2. The backend validates the ticker.
3. The agent collects news, prices, and company data.
4. Gemini analyzes the information.
5. FastAPI streams the result to the frontend.
6. The completed analysis and source links are stored in Supabase.

## Project Structure

```text
catalystedge-ai/
├── frontend/                 # React frontend
├── stocksense/
│   ├── agents/              # Bull, Bear, Skeptic, Synthesizer
│   ├── api/                 # FastAPI routes
│   ├── core/                # Data collection and analysis
│   ├── db/                  # Supabase integration
│   └── orchestration/       # ReAct and streaming flows
├── supabase/                 # Schema and migrations
├── tests/
├── requirements.txt
└── readme.md
```

## Local Setup

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your keys to `.env`:

```env
GOOGLE_API_KEY=your_google_api_key
NEWSAPI_KEY=your_newsapi_key
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key
```

Run the Supabase files in this order:

```text
supabase/schema.sql
supabase/migrations/001_stage4_features.sql
supabase/migrations/002_phase2_watchman.sql
supabase/migrations/003_analysis_cache.sql
supabase/migrations/004_news_sources.sql
```

### Frontend

```bash
cd frontend
npm install
```

Set the frontend API URL:

```env
VITE_API_URL=http://127.0.0.1:8000
```

## Run Locally

Start the backend:

```bash
cd ~/catalystedge-ai
source venv/bin/activate
python -m stocksense.main
```

Start the frontend in another Terminal:

```bash
cd ~/catalystedge-ai/frontend
npm run dev
```

Open `http://localhost:3000`.

## Validation

```bash
python3 -m compileall stocksense

cd frontend
npm run typecheck
npm run build
```

## Status

The project currently works locally. The stock analysis flow, company search, price movement card, history, Supabase caching, and clickable article citations have been implemented and tested.

Deployment will be added later.

## Disclaimer

CatalystEdge AI is an educational and portfolio project. It does not provide financial advice.

## Author

**Sravya Nallagantula**

- GitHub: https://github.com/SravyaNallagantula
- LinkedIn: https://www.linkedin.com/in/sravyanallagantula/
- Email: nsravya16@gmail.com
