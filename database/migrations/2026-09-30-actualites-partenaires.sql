-- Migration d'une base existante : vignettes et import automatique des actualités, partenaires officiels.
-- Ne supprime rien. À lancer une fois (phpMyAdmin ou mysql < fichier).
ALTER TABLE news
    ADD COLUMN image_path    VARCHAR(120) NULL AFTER source_url,
    ADD COLUMN origin        ENUM('manual','feed') NOT NULL DEFAULT 'manual' AFTER image_path,
    ADD COLUMN external_guid VARCHAR(191) NULL UNIQUE AFTER origin;

CREATE TABLE IF NOT EXISTS partners (
    id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(120) NOT NULL,
    url          VARCHAR(300) NULL,
    tier         ENUM('officiel','media','plateforme','institution') NOT NULL DEFAULT 'officiel',
    description  VARCHAR(240) NULL,
    logo_path    VARCHAR(120) NULL,
    sort_order   SMALLINT NOT NULL DEFAULT 0,
    is_active    TINYINT(1) NOT NULL DEFAULT 1,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
