-- Historique hebdomadaire des compteurs de réseaux sociaux.
CREATE TABLE IF NOT EXISTS stats_reseaux (
    date DATE NOT NULL,
    reseau TEXT NOT NULL,
    cle TEXT NOT NULL,
    valeur TEXT NOT NULL,
    PRIMARY KEY (date, reseau, cle)
);
CREATE INDEX IF NOT EXISTS stats_reseaux_recherche ON stats_reseaux (reseau, cle, date DESC);
