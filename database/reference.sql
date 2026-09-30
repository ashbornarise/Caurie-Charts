-- Cauri Charts : données de référence RÉELLES (pays, classements, versions de la formule).
-- Aucune donnée d'artiste : le catalogue vient des imports et des déclarations. Généré par bin/generate-seed.php.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

INSERT INTO countries (id, code, name_fr, name_en, locale, chart_size, platforms, is_pilot, sort_order) VALUES
(1, 'TG', 'Togo', 'Togo', 'fr', 20, 'youtube,audiomack,boomplay', 1, 1),
(2, 'BJ', 'Bénin', 'Benin', 'fr', 10, 'youtube,audiomack,boomplay', 0, 2),
(3, 'GH', 'Ghana', 'Ghana', 'en', 10, 'youtube,audiomack,boomplay', 0, 3),
(4, 'CI', 'Côte d''Ivoire', 'Côte d''Ivoire', 'fr', 10, 'youtube,audiomack,boomplay', 0, 4),
(5, 'SN', 'Sénégal', 'Senegal', 'fr', 10, 'youtube,audiomack,boomplay', 0, 5);
INSERT INTO chart_types (id, code, name, kind, is_public, is_computed, is_regional, sort_order) VALUES
(1, 'prime', 'Prime Chart', 'tracks', 1, 1, 0, 1),
(2, 'buzz', 'Buzz Chart', 'tracks', 1, 1, 0, 2),
(3, 'fresh', 'Fresh Chart', 'tracks', 1, 1, 0, 3),
(4, 'icon', 'Icon Chart', 'artists', 1, 1, 0, 4),
(5, 'legend', 'Legend Chart', 'tracks', 1, 1, 0, 5),
(6, 'vintage', 'Vintage Chart', 'tracks', 0, 0, 0, 6),
(7, 'prime-wa', 'Prime Chart Afrique de l''Ouest', 'tracks', 1, 1, 1, 7);
INSERT INTO formula_versions (version, formula_json, effective_from, note) VALUES
(1, '{"version":1,"weights":{"audio":1,"youtube":0.5,"declaration":1},"country_weights":[],"chart_depth":100,"chart_weights":{"apple_music":0,"audiomack":0,"boomplay":0},"diversity":{"top":5,"min_sources":2},"anti_fraud":{"spike_factor":5,"spike_history_weeks":4,"spike_min_history":2,"declaration_tolerance":0.3,"youtube_min_views":10000,"youtube_min_likes_per_1000":1,"youtube_max_likes_per_1000":250},"buzz":{"min_growth_pct":50,"min_score":2000},"fresh":{"max_age_days":56}}', '2026-01-01', 'Formule de départ (METHODOLOGIE.md v1.1)'),
(2, '{"version":2,"weights":{"audio":1,"youtube":0.5,"declaration":1},"country_weights":[],"chart_depth":100,"chart_weights":{"apple_music":150,"audiomack":150,"boomplay":150},"diversity":{"top":5,"min_sources":2},"anti_fraud":{"spike_factor":5,"spike_history_weeks":4,"spike_min_history":2,"declaration_tolerance":0.3,"youtube_min_views":10000,"youtube_min_likes_per_1000":1,"youtube_max_likes_per_1000":250},"buzz":{"min_growth_pct":50,"min_score":2000},"fresh":{"max_age_days":56}}', '2026-10-12', 'Méthodologie v1.2 : les positions dans les classements Apple Music, Audiomack et Boomplay rapportent des points (150 par point de position, à valider après quatre semaines).');
SET FOREIGN_KEY_CHECKS = 1;
