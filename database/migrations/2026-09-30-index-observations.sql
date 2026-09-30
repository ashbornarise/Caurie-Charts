-- Index pour les fenêtres de temps des classements en direct (semaine, mois, année, tout temps). Ne supprime rien.
ALTER TABLE chart_observations ADD INDEX idx_obs_day (observed_on, source, country_id);
