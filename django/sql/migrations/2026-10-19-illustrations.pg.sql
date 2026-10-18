CREATE TABLE IF NOT EXISTS illustrations (
    id BIGSERIAL PRIMARY KEY,
    famille VARCHAR(24) NOT NULL,
    sujet_hash VARCHAR(64) NOT NULL,
    fichier VARCHAR(240) NOT NULL,
    cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    utilise_le TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS illustrations_banque ON illustrations (famille, utilise_le, cree_le);
CREATE INDEX IF NOT EXISTS illustrations_jour ON illustrations (cree_le);
