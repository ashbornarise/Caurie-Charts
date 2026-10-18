-- Autorisation TikTok : le code reçu sur Vercel est échangé par GitHub Actions.
CREATE TABLE IF NOT EXISTS tiktok_auth (
    id BIGSERIAL PRIMARY KEY,
    code TEXT,
    state TEXT,
    recu_le TIMESTAMPTZ,
    access_token TEXT,
    refresh_token TEXT,
    access_expire TIMESTAMPTZ,
    refresh_expire TIMESTAMPTZ,
    open_id TEXT,
    maj_le TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS tiktok_auth_code_recu ON tiktok_auth (recu_le DESC) WHERE code IS NOT NULL;
