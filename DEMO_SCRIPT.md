# CatalystEdge AI Demo Script

## 1. Problem
Investors often see a stock move but do not immediately know which news, price action, or fundamentals are driving it.

## 2. Solution
CatalystEdge AI analyzes a ticker using:
- News headlines
- Historical price data
- Company fundamentals
- AI sentiment analysis
- Skeptic and risk review

## 3. Demo Flow
1. Open the CatalystEdge AI dashboard.
2. Enter AAPL.
3. Click WHY IS IT MOVING?
4. Show the bullish sentiment and confidence.
5. Explain the main catalysts.
6. Show the reasoning steps.
7. Open RISK_SIGNALS to show the skeptic analysis.
8. Mention that results are cached in Supabase.

## 4. Architecture
- React + TypeScript frontend
- FastAPI backend
- LangGraph ReAct workflow
- Google Gemini
- NewsAPI
- yfinance
- Supabase PostgreSQL

## 5. Closing
CatalystEdge AI turns fragmented market information into an explainable, evidence-based stock movement summary.
