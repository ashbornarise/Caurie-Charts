-- Cauri Charts : schéma MySQL / MariaDB (utf8mb4)
-- Import : mysql -u root cauricharts < database/schema.sql  (ou php bin/install.php)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS social_posts, partners, chart_observations, news, contact_messages, api_quota, audit_log, login_attempts, users,
    track_reviews, weekly_scores, chart_entries, chart_runs, chart_types, formula_versions,
    submissions, snapshots, track_platform_ids, tracks, artists, countries;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE countries (
    id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code         CHAR(2)      NOT NULL UNIQUE,
    name_fr      VARCHAR(80)  NOT NULL,
    name_en      VARCHAR(80)  NOT NULL,
    locale       VARCHAR(5)   NOT NULL DEFAULT 'fr',
    chart_size   TINYINT UNSIGNED NOT NULL DEFAULT 10,
    platforms    VARCHAR(255) NOT NULL DEFAULT 'youtube',  -- plateformes actives, séparées par des virgules
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    is_pilot     TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order   TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE artists (
    id                     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                   VARCHAR(150) NOT NULL,
    slug                   VARCHAR(160) NOT NULL UNIQUE,
    submission_country_id  SMALLINT UNSIGNED NOT NULL,  -- pays où l'artiste soumet sa musique (fait foi)
    label_owner            VARCHAR(50)  NULL,           -- 'novaluz' = artiste du label du groupe (badge)
    is_emerging            TINYINT(1)   NOT NULL DEFAULT 0,
    -- active : classé ; pending : découvert par l'import, pays à confirmer ; out_of_scope : hors des pays couverts
    status                 ENUM('active','pending','out_of_scope') NOT NULL DEFAULT 'active',
    guessed_country_id     SMALLINT UNSIGNED NULL,      -- pays suggéré par l'import (classements où il apparaît)
    match_key              VARCHAR(160) NULL,           -- nom normalisé, pour rapprocher les imports
    top_country_id         SMALLINT UNSIGNED NULL,      -- pays d'écoute principal (statistique déclarée)
    top_country_share      DECIMAL(5,2) NULL,
    top_country_updated_at DATE NULL,
    bio                    TEXT NULL,
    image_url              VARCHAR(500) NULL,
    deezer_id              BIGINT UNSIGNED NULL,        -- profil Deezer (photo, nombre de fans)
    spotify_id             VARCHAR(40) NULL,            -- profil Spotify (identifiant public, Wikidata)
    fans                   INT UNSIGNED NULL,           -- fans Deezer au dernier relevé
    youtube_channel_id     VARCHAR(40) NULL,            -- chaîne officielle (Wikidata, clip, recherche)
    youtube_subscribers    INT UNSIGNED NULL,           -- abonnés YouTube au dernier relevé
    channel_checked_at     DATETIME NULL,               -- dernière synchronisation de la chaîne (clips de l'artiste)
    discovered_via         VARCHAR(160) NULL,           -- comment l'artiste a été trouvé (classement, Wikidata, réseau Deezer…)
    profile_checked_at     DATETIME NULL,
    origin_country         CHAR(2) NULL,                -- pays d'origine selon MusicBrainz (code ISO), indicatif
    base_country           CHAR(2) NULL,                -- pays où la carrière est basée (fait foi pour le classement)
    origin_source          VARCHAR(20) NULL,            -- musicbrainz, ia, admin
    origin_confidence      DECIMAL(3,2) NULL,
    origin_note            VARCHAR(1000) NULL,          -- justification et sources consultées
    origin_checked_at      DATETIME NULL,
    created_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_artist_country FOREIGN KEY (submission_country_id) REFERENCES countries(id),
    CONSTRAINT fk_artist_top_country FOREIGN KEY (top_country_id) REFERENCES countries(id),
    INDEX idx_artist_country (submission_country_id),
    INDEX idx_artist_match (match_key),
    INDEX idx_artist_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tracks (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    slug          VARCHAR(220) NOT NULL UNIQUE,
    artist_id     INT UNSIGNED NOT NULL,        -- artiste principal
    featuring     VARCHAR(255) NULL,
    release_date  DATE NULL,
    cover_url     VARCHAR(500) NULL,
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    match_key     VARCHAR(255) NULL,          -- artiste + titre normalisés, pour rapprocher les imports
    youtube_checked_at DATETIME NULL,         -- dernière recherche automatique du clip
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_track_artist FOREIGN KEY (artist_id) REFERENCES artists(id),
    INDEX idx_track_artist (artist_id),
    INDEX idx_track_match (match_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Identifiants d'un titre sur chaque plateforme. Clip, audio officiel, lyrics, live et
-- remixes rattachés au même titre comptent ensemble (METHODOLOGIE.md, section 2).
CREATE TABLE track_platform_ids (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id      INT UNSIGNED NOT NULL,
    platform      ENUM('youtube','audiomack','boomplay','spotify','apple_music','deezer') NOT NULL,
    external_id   VARCHAR(191) NOT NULL,
    kind          VARCHAR(30)  NOT NULL DEFAULT 'main',  -- clip, audio, art_track, lyrics, live, remix, main
    url           VARCHAR(500) NULL,
    published_at  DATE NULL,
    is_official   TINYINT(1) NOT NULL DEFAULT 1,
    -- manual : saisi par l'équipe ; auto : trouvé par l'import ou la recherche YouTube ; confirmed : vérifié
    match_status  ENUM('manual','auto','confirmed') NOT NULL DEFAULT 'manual',
    CONSTRAINT fk_tpi_track FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    UNIQUE KEY uq_platform_external (platform, external_id),
    INDEX idx_tpi_track (track_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Relevé quotidien des compteurs cumulés
CREATE TABLE snapshots (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_platform_id  INT UNSIGNED NOT NULL,
    captured_on        DATE NOT NULL,
    plays              BIGINT UNSIGNED NOT NULL,  -- vues ou écoutes cumulées
    likes              BIGINT UNSIGNED NULL,
    comments           BIGINT UNSIGNED NULL,
    popularity         TINYINT UNSIGNED NULL,     -- indice Spotify (0-100), hors score
    source             ENUM('api','manual') NOT NULL DEFAULT 'api',
    created_by         INT UNSIGNED NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_snap_tpi FOREIGN KEY (track_platform_id) REFERENCES track_platform_ids(id) ON DELETE CASCADE,
    UNIQUE KEY uq_snap_day (track_platform_id, captured_on),
    INDEX idx_snap_day (captured_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Déclarations d'artistes et de labels (captures d'écran)
CREATE TABLE submissions (
    id                     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id               INT UNSIGNED NULL,
    artist_id              INT UNSIGNED NULL,
    submitted_artist_name  VARCHAR(150) NOT NULL,
    submitted_track_title  VARCHAR(200) NOT NULL,
    contact_name           VARCHAR(150) NOT NULL,
    contact_email          VARCHAR(190) NOT NULL,
    platform               VARCHAR(30)  NOT NULL,
    period_start           DATE NOT NULL,
    period_end             DATE NOT NULL,
    streams                BIGINT UNSIGNED NOT NULL,
    country_breakdown      TEXT NULL,     -- JSON {"TG": 62.5, "BJ": 20, ...} en %
    screenshot_path        VARCHAR(255) NOT NULL,  -- fichier dans storage/uploads (hors public)
    status                 ENUM('pending','validated','rejected') NOT NULL DEFAULT 'pending',
    reviewed_by            INT UNSIGNED NULL,
    reviewed_at            DATETIME NULL,
    review_note            TEXT NULL,
    ip_hash                CHAR(64) NULL,
    created_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sub_track FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE SET NULL,
    CONSTRAINT fk_sub_artist FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE SET NULL,
    INDEX idx_sub_status (status),
    INDEX idx_sub_track_period (track_id, period_start, period_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Versions de la formule : chaque calcul enregistre la version utilisée
CREATE TABLE formula_versions (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    version         INT UNSIGNED NOT NULL UNIQUE,
    formula_json    TEXT NOT NULL,
    effective_from  DATE NOT NULL,
    note            VARCHAR(500) NULL,
    created_by      INT UNSIGNED NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chart_types (
    id            TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(30) NOT NULL UNIQUE,
    name          VARCHAR(100) NOT NULL,
    kind          ENUM('tracks','artists') NOT NULL DEFAULT 'tracks',
    is_public     TINYINT(1) NOT NULL DEFAULT 0,
    is_computed   TINYINT(1) NOT NULL DEFAULT 0,
    is_regional   TINYINT(1) NOT NULL DEFAULT 0,
    sort_order    TINYINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Une exécution de calcul par classement, pays et période
CREATE TABLE chart_runs (
    id                   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    chart_type_id        TINYINT UNSIGNED NOT NULL,
    country_id           SMALLINT UNSIGNED NULL,   -- NULL = classement régional
    period_type          ENUM('week','month','year') NOT NULL,
    period_key           VARCHAR(10) NOT NULL,     -- 2026-W39, 2026-09, 2026
    period_start         DATE NOT NULL,
    period_end           DATE NOT NULL,
    formula_version      INT UNSIGNED NOT NULL,
    formula_json         TEXT NOT NULL,
    methodology_version  VARCHAR(10) NOT NULL,
    status               ENUM('draft','published') NOT NULL DEFAULT 'draft',
    is_provisional       TINYINT(1) NOT NULL DEFAULT 0,
    computed_at          DATETIME NOT NULL,
    published_at         DATETIME NULL,
    published_by         INT UNSIGNED NULL,
    correction_note      TEXT NULL,
    corrected_at         DATETIME NULL,
    CONSTRAINT fk_run_type FOREIGN KEY (chart_type_id) REFERENCES chart_types(id),
    CONSTRAINT fk_run_country FOREIGN KEY (country_id) REFERENCES countries(id),
    UNIQUE KEY uq_run (chart_type_id, country_id, period_type, period_key),
    INDEX idx_run_lookup (country_id, period_type, status, period_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chart_entries (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    chart_run_id       INT UNSIGNED NOT NULL,
    position           SMALLINT UNSIGNED NOT NULL,
    track_id           INT UNSIGNED NULL,
    artist_id          INT UNSIGNED NULL,
    score              DECIMAL(18,2) NOT NULL,
    previous_position  SMALLINT UNSIGNED NULL,
    peak_position      SMALLINT UNSIGNED NOT NULL,
    weeks_on_chart     SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    sources_count      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    growth_pct         DECIMAL(10,2) NULL,
    flags              TEXT NULL,   -- JSON
    details            TEXT NULL,   -- JSON (répartition par source)
    CONSTRAINT fk_entry_run FOREIGN KEY (chart_run_id) REFERENCES chart_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_entry_track FOREIGN KEY (track_id) REFERENCES tracks(id),
    CONSTRAINT fk_entry_artist FOREIGN KEY (artist_id) REFERENCES artists(id),
    UNIQUE KEY uq_entry_pos (chart_run_id, position),
    INDEX idx_entry_track (track_id),
    INDEX idx_entry_artist (artist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Score hebdomadaire de chaque titre (base des classements mensuels, annuels et "tout temps")
CREATE TABLE weekly_scores (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id         INT UNSIGNED NOT NULL,
    country_id       SMALLINT UNSIGNED NOT NULL,
    week_start       DATE NOT NULL,
    score            DECIMAL(18,2) NOT NULL,
    sources_count    TINYINT UNSIGNED NOT NULL,
    breakdown        TEXT NOT NULL,   -- JSON
    flags            TEXT NOT NULL,   -- JSON
    review_status    ENUM('ok','pending','validated','excluded') NOT NULL DEFAULT 'ok',
    formula_version  INT UNSIGNED NOT NULL,
    computed_at      DATETIME NOT NULL,
    CONSTRAINT fk_ws_track FOREIGN KEY (track_id) REFERENCES tracks(id),
    CONSTRAINT fk_ws_country FOREIGN KEY (country_id) REFERENCES countries(id),
    UNIQUE KEY uq_ws (track_id, week_start),
    INDEX idx_ws_country_week (country_id, week_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Décisions d'un admin sur un titre signalé : validé (gardé) ou exclu (avec raison publique)
CREATE TABLE track_reviews (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id    INT UNSIGNED NOT NULL,
    week_start  DATE NOT NULL,
    decision    ENUM('validated','excluded') NOT NULL,
    reason      TEXT NOT NULL,
    user_id     INT UNSIGNED NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_review_track FOREIGN KEY (track_id) REFERENCES tracks(id),
    UNIQUE KEY uq_review (track_id, week_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email          VARCHAR(190) NOT NULL UNIQUE,
    name           VARCHAR(150) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('admin','editor') NOT NULL DEFAULT 'editor',
    totp_secret    VARCHAR(64) NULL,
    is_active      TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at  DATETIME NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE login_attempts (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ip            VARCHAR(45) NOT NULL,
    email         VARCHAR(190) NOT NULL,
    success       TINYINT(1) NOT NULL DEFAULT 0,
    attempted_at  DATETIME NOT NULL,
    INDEX idx_login_ip (ip, attempted_at),
    INDEX idx_login_email (email, attempted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_log (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      INT UNSIGNED NULL,
    action       VARCHAR(60) NOT NULL,
    entity_type  VARCHAR(40) NULL,
    entity_id    VARCHAR(40) NULL,
    reason       TEXT NULL,
    data         TEXT NULL,   -- JSON
    ip           VARCHAR(45) NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_date (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Compteur de quota journalier des API (YouTube : 10 000 unités par jour par défaut)
CREATE TABLE api_quota (
    api         VARCHAR(30) NOT NULL,
    day         DATE NOT NULL,
    units_used  INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (api, day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Contact et contestations (réponse sous sept jours)
CREATE TABLE contact_messages (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type         ENUM('contact','contestation') NOT NULL DEFAULT 'contact',
    name         VARCHAR(150) NOT NULL,
    email        VARCHAR(190) NOT NULL,
    subject      VARCHAR(200) NOT NULL,
    message      TEXT NOT NULL,
    status       ENUM('new','answered','closed') NOT NULL DEFAULT 'new',
    ip_hash      CHAR(64) NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Actualités publiées par l'équipe (encadré latéral et page /actualites)
CREATE TABLE news (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    slug          VARCHAR(220) NOT NULL UNIQUE,
    summary       VARCHAR(400) NOT NULL,
    body          TEXT NULL,
    category      ENUM('annonce','classement','sortie','evenement','industrie') NOT NULL DEFAULT 'annonce',
    country_id    SMALLINT UNSIGNED NULL,           -- NULL = tous pays
    source_name   VARCHAR(120) NULL,                -- actualité externe : citer la source
    source_url    VARCHAR(500) NULL,
    image_path    VARCHAR(120) NULL,                -- vignette locale (public/media/news), jamais un lien direct
    origin        ENUM('manual','feed') NOT NULL DEFAULT 'manual',
    external_guid VARCHAR(191) NULL UNIQUE,         -- identifiant de l'article dans le flux RSS
    status        ENUM('draft','published') NOT NULL DEFAULT 'draft',
    published_at  DATETIME NULL,
    created_by    INT UNSIGNED NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_news_country FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE SET NULL,
    INDEX idx_news_pub (status, published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Posts réseaux sociaux générés (3 par semaine), à valider avant publication
CREATE TABLE social_posts (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    slot_date     DATE NOT NULL,
    theme         VARCHAR(30) NOT NULL,
    title         VARCHAR(160) NOT NULL,
    caption       TEXT NOT NULL,
    hashtags      VARCHAR(300) NULL,
    facts         TEXT NOT NULL,                 -- JSON : les chiffres réels donnés à l'IA (vérification)
    image_square  VARCHAR(120) NULL,             -- public/media/social
    image_story   VARCHAR(120) NULL,
    carousel      TEXT NULL,                     -- JSON : diapositives 1080 × 1350 (couverture + une par performance)
    video         VARCHAR(120) NULL,             -- MP4 sans son construit à partir des diapositives
    status        ENUM('draft','approved','published','rejected') NOT NULL DEFAULT 'draft',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_post_slot (slot_date, theme)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Partenaires officiels (section de l'accueil et page /partenaires), gérés dans l'admin
CREATE TABLE partners (
    id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(120) NOT NULL,
    url          VARCHAR(300) NULL,
    tier         ENUM('officiel','media','plateforme','institution') NOT NULL DEFAULT 'officiel',
    description  VARCHAR(240) NULL,
    logo_path    VARCHAR(120) NULL,                 -- public/media/partners
    sort_order   SMALLINT NOT NULL DEFAULT 0,
    is_active    TINYINT(1) NOT NULL DEFAULT 1,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Positions relevées dans les classements des plateformes (Apple Music, Audiomack, Boomplay...)
-- Source de points de la méthodologie v1.2 : chaque jour de présence rapporte (profondeur + 1 - position).
CREATE TABLE chart_observations (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    source        VARCHAR(30) NOT NULL,          -- apple_music, audiomack, boomplay...
    country_id    SMALLINT UNSIGNED NOT NULL,    -- pays du classement observé
    observed_on   DATE NOT NULL,
    position      SMALLINT UNSIGNED NOT NULL,
    track_id      INT UNSIGNED NOT NULL,
    raw_title     VARCHAR(255) NOT NULL,
    raw_artist    VARCHAR(255) NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_obs_country FOREIGN KEY (country_id) REFERENCES countries(id),
    CONSTRAINT fk_obs_track FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    UNIQUE KEY uq_obs (source, country_id, observed_on, position),
    INDEX idx_obs_track_day (track_id, observed_on),
    INDEX idx_obs_day (observed_on, source, country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
