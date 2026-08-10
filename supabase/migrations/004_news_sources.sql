ALTER TABLE analysis_cache
ADD COLUMN IF NOT EXISTS news_articles JSONB DEFAULT '[]'::jsonb;
