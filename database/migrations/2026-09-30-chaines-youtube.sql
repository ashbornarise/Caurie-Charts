-- Synchronisation des chaînes YouTube des artistes (tous leurs clips, audios, lyrics, lives). Ne supprime rien.
ALTER TABLE artists ADD COLUMN channel_checked_at DATETIME NULL AFTER youtube_subscribers;
