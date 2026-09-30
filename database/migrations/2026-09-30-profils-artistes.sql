-- Migration d'une base existante : profils d'artistes enrichis par l'API publique Deezer. Ne supprime rien.
ALTER TABLE artists
    ADD COLUMN deezer_id          BIGINT UNSIGNED NULL AFTER image_url,
    ADD COLUMN fans               INT UNSIGNED NULL AFTER deezer_id,
    ADD COLUMN profile_checked_at DATETIME NULL AFTER fans;
ALTER TABLE artists
    ADD COLUMN origin_country     CHAR(2) NULL AFTER profile_checked_at,
    ADD COLUMN origin_checked_at  DATETIME NULL AFTER origin_country;
