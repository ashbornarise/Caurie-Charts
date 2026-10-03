-- Contacts des artistes pour l'envoi des distinctions : saisis par l'équipe (jamais devinés). Ajout seulement.
ALTER TABLE artists ADD COLUMN IF NOT EXISTS contact_email VARCHAR(190) NULL;
ALTER TABLE artists ADD COLUMN IF NOT EXISTS instagram VARCHAR(60) NULL;   -- identifiant sans @
ALTER TABLE award_distinctions ADD COLUMN IF NOT EXISTS emailed_at TIMESTAMP(0) NULL;
