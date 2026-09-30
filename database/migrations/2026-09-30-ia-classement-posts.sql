-- Migration d'une base existante : classement automatique des artistes (MusicBrainz + IA) et posts réseaux sociaux. Ne supprime rien.
ALTER TABLE artists
    ADD COLUMN base_country      CHAR(2) NULL AFTER origin_country,
    ADD COLUMN origin_source     VARCHAR(20) NULL AFTER base_country,
    ADD COLUMN origin_confidence DECIMAL(3,2) NULL AFTER origin_source,
    ADD COLUMN origin_note       VARCHAR(1000) NULL AFTER origin_confidence;

CREATE TABLE IF NOT EXISTS social_posts (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    slot_date     DATE NOT NULL,
    theme         VARCHAR(30) NOT NULL,
    title         VARCHAR(160) NOT NULL,
    caption       TEXT NOT NULL,
    hashtags      VARCHAR(300) NULL,
    facts         TEXT NOT NULL,                 -- JSON : les chiffres réels donnés à l'IA (vérification)
    image_square  VARCHAR(120) NULL,             -- public/media/social
    image_story   VARCHAR(120) NULL,
    status        ENUM('draft','approved','published','rejected') NOT NULL DEFAULT 'draft',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_post_slot (slot_date, theme)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
