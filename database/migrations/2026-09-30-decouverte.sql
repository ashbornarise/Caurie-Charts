-- Découverte automatique des artistes : chaîne YouTube et nombre d'abonnés (fanbase). Ne supprime rien.
ALTER TABLE artists
    ADD COLUMN youtube_channel_id  VARCHAR(40) NULL AFTER fans,
    ADD COLUMN youtube_subscribers INT UNSIGNED NULL AFTER youtube_channel_id,
    ADD COLUMN discovered_via      VARCHAR(160) NULL AFTER youtube_subscribers;
