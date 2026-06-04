-- 给已有 resumes 表添加新字段
-- 在 Supabase SQL Editor 中执行

ALTER TABLE resumes ADD COLUMN IF NOT EXISTS birth_year TEXT;
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS birth_date TEXT;
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS photo TEXT;

-- 启用实时同步
ALTER PUBLICATION supabase_realtime ADD TABLE resumes;
