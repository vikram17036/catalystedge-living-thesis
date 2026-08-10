-- CatalystEdge / StockSense — FULL bootstrap for a NEW Supabase project
-- Run once in: Dashboard → SQL Editor → New query → Run
-- Order: base schema + migrations 001–005


-- ========== schema.sql ==========

-- StockSense Database Schema
-- Stage 3: User Belief System
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USER PROFILES
-- ============================================
-- Extends Supabase auth.users with app-specific data
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================
-- POSITIONS (Watchlist with context)
-- ============================================
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    position_type TEXT CHECK (position_type IN ('long', 'short', 'watching')) DEFAULT 'watching',
    entry_date DATE,
    entry_price DECIMAL(12, 4),
    current_shares DECIMAL(12, 4),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, ticker)
);

-- ============================================
-- THESES (Investment theses with kill criteria)
-- ============================================
CREATE TABLE IF NOT EXISTS theses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    
    -- Core thesis
    thesis_summary TEXT NOT NULL,  -- "Why I own this"
    conviction_level TEXT CHECK (conviction_level IN ('high', 'medium', 'low')) DEFAULT 'medium',
    
    -- Kill criteria (Stage 3 core feature)
    kill_criteria TEXT[],  -- Array of conditions that would trigger exit
    
    -- Analysis-Thesis Linkage (Stage 4)
    origin_analysis_id INTEGER,               -- SQLite cache ID when thesis was created
    origin_analysis_snapshot JSONB,           -- Snapshot of key metrics at thesis creation
    -- Snapshot includes: {sentiment, confidence, key_themes, skeptic_verdict, timestamp}
    
    -- Thesis metadata
    time_horizon TEXT CHECK (time_horizon IN ('short', 'medium', 'long')) DEFAULT 'medium',
    thesis_type TEXT CHECK (thesis_type IN ('growth', 'value', 'income', 'turnaround', 'special_situation')) DEFAULT 'growth',
    
    -- Status tracking
    status TEXT CHECK (status IN ('active', 'validated', 'invalidated', 'exited')) DEFAULT 'active',
    invalidation_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- THESIS HISTORY (Track belief evolution)
-- ============================================
CREATE TABLE IF NOT EXISTS thesis_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Snapshot of thesis at this point
    thesis_summary TEXT NOT NULL,
    conviction_level TEXT,
    kill_criteria TEXT[],
    
    -- What changed
    change_reason TEXT,
    change_type TEXT CHECK (change_type IN ('created', 'updated', 'conviction_changed', 'invalidated', 'exited')),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- KILL ALERTS (Kill criteria monitoring - Stage 4)
-- ============================================
-- Alerts generated when analysis results may trigger kill criteria
CREATE TABLE IF NOT EXISTS kill_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    
    -- What triggered the alert
    triggered_criteria TEXT NOT NULL,           -- The kill criteria text that was matched
    triggering_signal TEXT NOT NULL,            -- The signal from analysis that matched
    match_confidence DECIMAL(3, 2),             -- 0.00-1.00 confidence in the match
    
    -- Analysis context
    analysis_sentiment TEXT,                    -- Sentiment at time of alert
    analysis_confidence DECIMAL(3, 2),          -- Confidence at time of alert
    analysis_summary TEXT,                      -- Brief summary for context
    
    -- Alert status
    status TEXT CHECK (status IN ('pending', 'dismissed', 'acknowledged', 'acted')) DEFAULT 'pending',
    user_action TEXT,                           -- What action user took (if any)
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================
-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE theses ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE kill_alerts ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can only see/edit their own profile
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- Positions: Users can only see/edit their own positions
CREATE POLICY "Users can view own positions" ON positions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own positions" ON positions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own positions" ON positions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own positions" ON positions
    FOR DELETE USING (auth.uid() = user_id);

-- Theses: Users can only see/edit their own theses
CREATE POLICY "Users can view own theses" ON theses
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own theses" ON theses
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own theses" ON theses
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own theses" ON theses
    FOR DELETE USING (auth.uid() = user_id);

-- Thesis History: Users can only see their own history
CREATE POLICY "Users can view own thesis history" ON thesis_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own thesis history" ON thesis_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Kill Alerts: Users can see/manage their own alerts
CREATE POLICY "Users can view own kill alerts" ON kill_alerts
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own kill alerts" ON kill_alerts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own kill alerts" ON kill_alerts
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own kill alerts" ON kill_alerts
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================
-- INDEXES for performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_theses_user_id ON theses(user_id);
CREATE INDEX IF NOT EXISTS idx_theses_ticker ON theses(ticker);
CREATE INDEX IF NOT EXISTS idx_theses_status ON theses(status);
CREATE INDEX IF NOT EXISTS idx_thesis_history_thesis_id ON thesis_history(thesis_id);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_user_id ON kill_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_thesis_id ON kill_alerts(thesis_id);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_ticker ON kill_alerts(ticker);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_status ON kill_alerts(status);

-- ============================================
-- UPDATED_AT TRIGGER
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_theses_updated_at
    BEFORE UPDATE ON theses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ========== migrations\001_stage4_features.sql ==========

-- ============================================
-- StockSense Migration: Stage 4 Features
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. Add origin_analysis columns to theses table (Feature 2)
ALTER TABLE theses 
ADD COLUMN IF NOT EXISTS origin_analysis_id INTEGER,
ADD COLUMN IF NOT EXISTS origin_analysis_snapshot JSONB;

-- Add comment for documentation
COMMENT ON COLUMN theses.origin_analysis_id IS 'SQLite cache ID when thesis was created';
COMMENT ON COLUMN theses.origin_analysis_snapshot IS 'Snapshot of key metrics at thesis creation: {sentiment, confidence, key_themes, skeptic_verdict, timestamp}';


-- 2. Create kill_alerts table (Feature 1)
CREATE TABLE IF NOT EXISTS kill_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    
    -- What triggered the alert
    triggered_criteria TEXT NOT NULL,
    triggering_signal TEXT NOT NULL,
    match_confidence DECIMAL(3, 2),
    
    -- Analysis context
    analysis_sentiment TEXT,
    analysis_confidence DECIMAL(3, 2),
    analysis_summary TEXT,
    
    -- Alert status
    status TEXT CHECK (status IN ('pending', 'dismissed', 'acknowledged', 'acted')) DEFAULT 'pending',
    user_action TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);


-- 3. Enable RLS on kill_alerts
ALTER TABLE kill_alerts ENABLE ROW LEVEL SECURITY;


-- 4. Create RLS policies for kill_alerts (idempotent)
DROP POLICY IF EXISTS "Users can view own kill alerts" ON kill_alerts;
CREATE POLICY "Users can view own kill alerts" ON kill_alerts
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own kill alerts" ON kill_alerts;
CREATE POLICY "Users can insert own kill alerts" ON kill_alerts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own kill alerts" ON kill_alerts;
CREATE POLICY "Users can update own kill alerts" ON kill_alerts
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own kill alerts" ON kill_alerts;
CREATE POLICY "Users can delete own kill alerts" ON kill_alerts
    FOR DELETE USING (auth.uid() = user_id);


-- 5. Create indexes for kill_alerts
CREATE INDEX IF NOT EXISTS idx_kill_alerts_user_id ON kill_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_thesis_id ON kill_alerts(thesis_id);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_ticker ON kill_alerts(ticker);
CREATE INDEX IF NOT EXISTS idx_kill_alerts_status ON kill_alerts(status);


-- Verify migration
SELECT 'Migration complete!' as status;
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'theses' 
AND column_name IN ('origin_analysis_id', 'origin_analysis_snapshot');


-- ========== migrations\002_phase2_watchman.sql ==========

-- Create alert_history table for Phase 2: The Watchman Update
CREATE TABLE IF NOT EXISTS public.alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    thesis_id UUID NOT NULL REFERENCES public.theses(id),
    ticker TEXT NOT NULL,
    alert_type TEXT NOT NULL DEFAULT 'kill_criteria', -- 'kill_criteria', 'price_movement', 'news_sentiment'
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}'::jsonb, -- Stores full context (triggered criteria, signal, confidence)
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.alert_history ENABLE ROW LEVEL SECURITY;

-- Policy: Users can see their own alerts
CREATE POLICY "Users can view their own alerts" 
    ON public.alert_history FOR SELECT 
    USING (auth.uid() = user_id);

-- Policy: Service role can insert alerts (for background jobs)
-- Note: In Supabase, the service role bypasses RLS, so explicit insert policy for users isn't strictly needed for background jobs,
-- but if we want users to create alerts (e.g. manual trigger), we might need it. 
-- For now, we assume alerts are system-generated or background-generated.


-- ========== migrations\003_analysis_cache.sql ==========

-- Migration: Add analysis_cache table to Supabase
-- This replaces the local SQLite cache with Supabase storage
-- Run this in Supabase SQL Editor

-- ============================================
-- ANALYSIS CACHE (replaces SQLite)
-- ============================================
-- Public cache for stock analysis results
-- No RLS - accessible by all users (cached analyses are public)

CREATE TABLE IF NOT EXISTS analysis_cache (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    analysis_summary TEXT,
    sentiment_report TEXT,
    
    -- JSON-serialized data
    price_data JSONB DEFAULT '[]'::jsonb,
    headlines JSONB DEFAULT '[]'::jsonb,
    reasoning_steps JSONB DEFAULT '[]'::jsonb,
    tools_used JSONB DEFAULT '[]'::jsonb,
    
    -- Analysis metadata
    iterations INTEGER DEFAULT 0,
    
    -- Structured sentiment analysis (Stage 1)
    overall_sentiment TEXT,
    overall_confidence DECIMAL(3, 2),
    confidence_reasoning TEXT,
    headline_analyses JSONB DEFAULT '[]'::jsonb,
    key_themes JSONB DEFAULT '[]'::jsonb,
    potential_impact TEXT,
    risks_identified JSONB DEFAULT '[]'::jsonb,
    information_gaps JSONB DEFAULT '[]'::jsonb,
    
    -- Skeptic analysis (Stage 2)
    skeptic_report TEXT,
    skeptic_sentiment TEXT,
    skeptic_confidence DECIMAL(3, 2),
    primary_disagreement TEXT,
    critiques JSONB DEFAULT '[]'::jsonb,
    bear_cases JSONB DEFAULT '[]'::jsonb,
    hidden_risks JSONB DEFAULT '[]'::jsonb,
    would_change_mind JSONB DEFAULT '[]'::jsonb,
    
    -- Fundamental data
    fundamental_data JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast ticker lookups
CREATE INDEX IF NOT EXISTS idx_analysis_cache_ticker ON analysis_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_ticker_created ON analysis_cache(ticker, created_at DESC);

-- Updated_at trigger
CREATE TRIGGER update_analysis_cache_updated_at
    BEFORE UPDATE ON analysis_cache
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- PUBLIC ACCESS POLICY
-- ============================================
-- Analysis cache is public - anyone can read/write
-- This allows anonymous users to benefit from cached analyses

ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY;

-- Allow anyone to read cached analyses
CREATE POLICY "Anyone can read analysis cache" ON analysis_cache
    FOR SELECT USING (true);

-- Allow backend to insert (using service key or anon key)
CREATE POLICY "Anyone can insert analysis cache" ON analysis_cache
    FOR INSERT WITH CHECK (true);

-- Allow backend to delete (using service key)
CREATE POLICY "Anyone can delete analysis cache" ON analysis_cache
    FOR DELETE USING (true);

-- Note: For production, you may want to restrict write access
-- to only authenticated service roles by checking:
-- auth.role() = 'service_role' OR auth.role() = 'authenticated'


-- ========== migrations\004_news_sources.sql ==========

ALTER TABLE analysis_cache
ADD COLUMN IF NOT EXISTS news_articles JSONB DEFAULT '[]'::jsonb;


-- ========== migrations\005_living_thesis.sql ==========

-- Living Thesis Phase 0: single alerts model + replay support
-- Run in YOUR Supabase SQL editor after base schema + migrations 001-004

-- Unified alerts table (API, scheduler, replay, dashboard)
create table if not exists public.thesis_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  thesis_id uuid not null references public.theses(id) on delete cascade,
  ticker text not null,
  severity text not null default 'warning'
    check (severity in ('info', 'warning', 'critical')),
  status text not null default 'unread'
    check (status in ('unread', 'read', 'acknowledged', 'dismissed')),
  title text not null,
  message text not null,
  triggered_criteria jsonb not null default '[]'::jsonb,
  diff jsonb,
  evidence_ids jsonb not null default '[]'::jsonb,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_thesis_alerts_user on public.thesis_alerts(user_id);
create index if not exists idx_thesis_alerts_thesis on public.thesis_alerts(thesis_id);
create index if not exists idx_thesis_alerts_status on public.thesis_alerts(user_id, status);

alter table public.thesis_alerts enable row level security;

create policy "Users select own thesis_alerts"
  on public.thesis_alerts for select
  using (auth.uid() = user_id);

create policy "Users update own thesis_alerts"
  on public.thesis_alerts for update
  using (auth.uid() = user_id);

create policy "Users delete own thesis_alerts"
  on public.thesis_alerts for delete
  using (auth.uid() = user_id);

-- Service role inserts alerts from scheduler / replay (bypasses RLS)

-- Structured origin snapshot + version on theses (idempotent)
alter table public.theses
  add column if not exists origin_evidence jsonb default '[]'::jsonb;

alter table public.theses
  add column if not exists structured_kill_criteria jsonb default '[]'::jsonb;

alter table public.theses
  add column if not exists thesis_version int default 1;

-- Replay fixtures (demo + tests) â€” not user-facing RLS required for service role
create table if not exists public.replay_snapshots (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  label text not null,
  as_of timestamptz not null,
  evidence jsonb not null default '[]'::jsonb,
  analysis_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_replay_snapshots_ticker on public.replay_snapshots(ticker);

-- Phase 4: attached research (never mutate origin_evidence)
create table if not exists public.thesis_evidence (
  id uuid primary key default gen_random_uuid(),
  thesis_id uuid not null references public.theses(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  evidence_id text not null,
  evidence_type text not null
    check (evidence_type in ('event_study', 'backtest')),
  evidence jsonb not null,
  attached_at timestamptz not null default now(),
  unique (thesis_id, evidence_id)
);

create index if not exists idx_thesis_evidence_thesis on public.thesis_evidence(thesis_id);
create index if not exists idx_thesis_evidence_user on public.thesis_evidence(user_id);

alter table public.thesis_evidence enable row level security;

create policy "Users select own thesis_evidence"
  on public.thesis_evidence for select
  using (auth.uid() = user_id);

create policy "Users insert own thesis_evidence"
  on public.thesis_evidence for insert
  with check (auth.uid() = user_id);

create policy "Users delete own thesis_evidence"
  on public.thesis_evidence for delete
  using (auth.uid() = user_id);

grant select, insert, delete on table public.thesis_evidence to authenticated;
grant all on table public.thesis_evidence to service_role;

