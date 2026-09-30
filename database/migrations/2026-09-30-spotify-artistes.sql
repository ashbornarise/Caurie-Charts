-- Profil Spotify des artistes (identifiant public, via Wikidata). Ne supprime rien.
ALTER TABLE artists ADD COLUMN spotify_id VARCHAR(40) NULL AFTER deezer_id;
