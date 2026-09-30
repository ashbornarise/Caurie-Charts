-- Carrousels et vidéos des posts (diapositives style magazine). Ne supprime rien.
ALTER TABLE social_posts
    ADD COLUMN carousel TEXT NULL AFTER image_story,
    ADD COLUMN video VARCHAR(120) NULL AFTER carousel;
