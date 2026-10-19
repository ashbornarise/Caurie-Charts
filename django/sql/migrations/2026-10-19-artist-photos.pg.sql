-- Plans larges d'artistes validés à la main (tirés des clips officiels), pour les couvertures « lockup » (19/10/2026)
CREATE TABLE IF NOT EXISTS artist_photos (
    id BIGSERIAL PRIMARY KEY,
    artist_id BIGINT NOT NULL,
    fichier VARCHAR(240) NOT NULL,
    source VARCHAR(40) NOT NULL,
    source_ref VARCHAR(120),
    credit VARCHAR(300),
    plan_large BOOLEAN NOT NULL DEFAULT TRUE,
    valide_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    utilise_le TIMESTAMPTZ NULL
);
