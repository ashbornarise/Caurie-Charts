-- Cauri Studio : tâches de montage et passkeys (créées aussi à la volée par core/studio.py)
CREATE TABLE IF NOT EXISTS studio_jobs (
    id BIGSERIAL PRIMARY KEY, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(), lien TEXT NOT NULL, params TEXT NOT NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'attente', video TEXT, vignette TEXT, erreur TEXT, auteur BIGINT, post_id BIGINT
);
CREATE TABLE IF NOT EXISTS studio_passkeys (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, credential_id TEXT UNIQUE NOT NULL, public_key TEXT NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0, nom TEXT, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
