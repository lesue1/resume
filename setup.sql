-- 简历管理系统 - Supabase 建表 SQL
-- 在 Supabase SQL Editor 中执行: https://kihibtxvuimmrsrybpsf.supabase.co

CREATE TABLE IF NOT EXISTS resumes (
  id BIGSERIAL PRIMARY KEY,
  unique_code TEXT UNIQUE NOT NULL,
  name TEXT,
  gender TEXT,
  age TEXT,
  birth_year TEXT,
  birth_date TEXT,
  phone TEXT,
  email TEXT,
  city TEXT,
  school TEXT,
  degree TEXT,
  major TEXT,
  graduation_year TEXT,
  current_company TEXT,
  current_position TEXT,
  work_years TEXT,
  employment_status TEXT,
  current_salary TEXT,
  expected_salary TEXT,
  skills TEXT[],
  tech_direction TEXT,
  github TEXT,
  papers_link TEXT,
  has_top_papers BOOLEAN DEFAULT FALSE,
  source TEXT,
  target_position TEXT,
  interview_status TEXT DEFAULT '筛选中',
  hr_notes TEXT,
  resume_text TEXT,
  photo TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_follow_up TIMESTAMP WITH TIME ZONE
);

ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon" ON resumes
  FOR ALL USING (true)
  WITH CHECK (true);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_resumes_status ON resumes(interview_status);
CREATE INDEX IF NOT EXISTS idx_resumes_company ON resumes(current_company);
CREATE INDEX IF NOT EXISTS idx_resumes_degree ON resumes(degree);
CREATE INDEX IF NOT EXISTS idx_resumes_created ON resumes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resumes_tech ON resumes(tech_direction);
