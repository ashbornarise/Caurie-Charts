-- Cauri Monde : infos mondiales déjà jugées par le guetteur de flashs (chacune ne l'est qu'une fois)
CREATE TABLE IF NOT EXISTS monde_vus (
    cle    VARCHAR(16) PRIMARY KEY,
    vu_at  TIMESTAMP(0) NOT NULL DEFAULT CURRENT_TIMESTAMP
);
