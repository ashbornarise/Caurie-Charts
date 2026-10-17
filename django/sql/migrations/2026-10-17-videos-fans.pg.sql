-- Vidéos de concert proposées par les fans (formulaire /envoie-ta-video) : lien + autorisation écrite de publier avec crédit
CREATE TABLE IF NOT EXISTS fan_videos (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(190) NOT NULL,
    handle VARCHAR(120),
    artist VARCHAR(150) NOT NULL,
    event VARCHAR(200),
    city VARCHAR(120),
    event_date DATE,
    link VARCHAR(500) NOT NULL,
    consent SMALLINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'nouveau',
    ip_hash VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS fan_videos_status ON fan_videos (status, created_at);
