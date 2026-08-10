# CatalystEdge — Living Thesis Status

**Last updated:** 2026-08-09  
**Owner project:** `C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp`  
**GitHub:** https://github.com/vikram17036/catalystedge-living-thesis  
**Local stack:** Frontend `http://localhost:3002` (or 3000) → API `http://127.0.0.1:8002`  
**Production:** Frontend https://catalystedge-living-thesis-pearl.vercel.app · Backend https://catalystedge-backend.onrender.com

---

## 1. Product vision (locked)

CatalystEdge is **Living Market Thesis Intelligence**, not a stock chatbot.

**Permanent rules:**

1. Models interpret; tools calculate (no invented metrics / evidence IDs).
2. Replayability is first-class.
3. Deterministic kills / stats in code; qualitative needs citations (later).
4. No `exec()` of LLM-generated Python.

**Interview progression:**

> Phase 1: preserve and challenge a belief.  
> Phase 2: test whether a historical claim is true.  
> Phase 3: test what would have happened if you acted on a rule — without giving the LLM executable control.

---

## 2. Phase 1 — FROZEN

Live and verified. Thesis engine frozen except blocking production bugs.

Prod smoke: login → analyze NVDA → create thesis → replay adverse → Diff → WHY → kill banner → alerts.

| Piece | URL |
|-------|-----|
| Frontend | https://catalystedge-living-thesis-pearl.vercel.app |
| Backend | https://catalystedge-backend.onrender.com |

---

## 3. Phase 2 Event Study — FROZEN

**Status: locally verified; ship to prod with this freeze.** Research/Event Study code frozen except blocking bugs.

**Promise:** NL defines the experiment; typed contracts constrain it; deterministic code computes it; AI only interprets measured results.

**Local DoD (passed):**

```text
RESEARCH → What happens to NVDA around FOMC decisions?
        → Only rate hikes.
        → Compare five days before with five days after.
```

Kernel: `EventStudySpec` / pure engine / `fomc_v1` / sample accounting / price fingerprint / `research_routes` / RESEARCH UI.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_event_study.py tests/test_event_study_parse.py tests/test_event_study_interpret.py tests/test_thesis_loop.py tests/test_thesis_diff.py tests/test_contracts.py -q
```

**Prod smoke after deploy:** same three-turn RESEARCH on public URLs (+ Phase 1 quick regression).

---

## 4. What’s next — Phase 3 Strategy Lab (IN PROGRESS)

Long-only **SMA crossover only**. Typed `SmaCrossoverParams` (no free params dict). Signal at `t`, fill at `t+1`. Position sized including entry commission. Costs via counterfactual gross / commission-only / net. Daily MTM equity → max drawdown. No `exec()`, no RSI/breakout/Sharpe.

**Hero demo:**

1. “Backtest a 20/50 SMA crossover on NVDA since 2020.”
2. “Add 5 bps commission and 2 bps slippage.” → mutate costs, rerun
3. “Show max drawdown and hit rate.” → **no spec mutation**; surface metrics

Build gate: contracts → golden fixture → pure SMA engine → API/UI → DoD → **stop**.

---

## 5. How to start locally

```powershell
cd C:\Users\vikra\projects\catalystedge-ai-catalystedge-mvp
.\.venv\Scripts\uvicorn.exe stocksense.main:app --host 127.0.0.1 --port 8002

cd frontend
# VITE_API_URL=http://127.0.0.1:8002
npm run dev
```

---

## 6. Change log

1. Phase 0–1 Living Thesis shipped + production smoke.
2. Phase 1 frozen.
3. Phase 2 Event Study implemented + local three-turn demo green.
4. **Phase 2 frozen** (2026-08-09); Phase 3 Strategy Lab started.

---

*Source of truth for what’s done / what’s next.*
