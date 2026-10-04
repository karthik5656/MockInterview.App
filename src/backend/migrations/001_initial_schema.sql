-- 1. sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ NULL,
    resume_text TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    difficulty VARCHAR(20) NOT NULL CHECK (difficulty IN ('junior', 'mid', 'senior', 'staff')),
    include_topics TEXT[] NOT NULL DEFAULT '{}',
    exclude_topics TEXT[] NOT NULL DEFAULT '{}',
    max_questions INT NOT NULL DEFAULT 10 CHECK (max_questions > 0 AND max_questions <= 20),
    overall_score NUMERIC(3, 1) NULL CHECK (overall_score >= 0.0 AND overall_score <= 10.0)
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);

-- 2. questions table
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    idx INT NOT NULL CHECK (idx >= 1),
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_session_question_index UNIQUE (session_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_questions_session_id ON questions(session_id);

-- 3. answers table
CREATE TABLE IF NOT EXISTS answers (
    id UUID PRIMARY KEY,
    question_id UUID NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    transcript TEXT NOT NULL,
    audio_seconds NUMERIC(6, 2) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'evaluated', 'failed')),
    attempts INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_answers_session_id ON answers(session_id);
CREATE INDEX IF NOT EXISTS idx_answers_status ON answers(status);

-- 4. evaluations table
CREATE TABLE IF NOT EXISTS evaluations (
    answer_id UUID PRIMARY KEY REFERENCES answers(id) ON DELETE CASCADE,
    score INT NOT NULL CHECK (score >= 0 AND score <= 10),
    star JSONB NOT NULL,
    technical_depth JSONB NOT NULL,
    missing_points TEXT[] NOT NULL DEFAULT '{}',
    suggested_answer TEXT NOT NULL,
    model VARCHAR(100) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row-Level Security (RLS) policies
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service role full access on sessions') THEN
        CREATE POLICY "Service role full access on sessions" ON sessions FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service role full access on questions') THEN
        CREATE POLICY "Service role full access on questions" ON questions FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service role full access on answers') THEN
        CREATE POLICY "Service role full access on answers" ON answers FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service role full access on evaluations') THEN
        CREATE POLICY "Service role full access on evaluations" ON evaluations FOR ALL USING (true);
    END IF;
END $$;