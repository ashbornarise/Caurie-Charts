-- Photos des artistes en haute définition (Apple Music, photo presse envoyée par l'artiste) et verrou des photos
-- choisies à la main. Ajouts seulement : rien n'est supprimé ni modifié.
ALTER TABLE artists ADD COLUMN IF NOT EXISTS image_hd_url     VARCHAR(500) NULL;          -- photo pour les posts 4K
ALTER TABLE artists ADD COLUMN IF NOT EXISTS image_source     VARCHAR(20)  NULL;          -- deezer, apple, presse, admin
ALTER TABLE artists ADD COLUMN IF NOT EXISTS image_locked     SMALLINT     NOT NULL DEFAULT 0;  -- 1 : jamais remplacée la nuit
ALTER TABLE artists ADD COLUMN IF NOT EXISTS apple_id         BIGINT       NULL;          -- profil Apple Music de l'artiste
ALTER TABLE artists ADD COLUMN IF NOT EXISTS photo_checked_at TIMESTAMP(0) NULL;          -- dernière recherche de photo HD
ALTER TABLE artists ADD COLUMN IF NOT EXISTS photo_candidates TEXT NULL;  -- photos trouvées (JSON : source, url, taille, licence)
ALTER TABLE artists ADD COLUMN IF NOT EXISTS image_credit VARCHAR(250) NULL;  -- crédit obligatoire (licence libre de Wikimedia Commons)
