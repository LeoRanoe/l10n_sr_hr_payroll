-- migrate_res_company_exchange_rates.sql
-- Adds per-company exchange rate columns introduced in the currency-pair audit fix.
-- Safe to run multiple times (IF NOT EXISTS).
--
-- Usage on the VM:
--   sudo -u postgres psql -d YOUR_DB_NAME -f migrate_res_company_exchange_rates.sql

ALTER TABLE res_company
  ADD COLUMN IF NOT EXISTS sr_exchange_rate_usd double precision DEFAULT 36.5;

ALTER TABLE res_company
  ADD COLUMN IF NOT EXISTS sr_exchange_rate_eur double precision DEFAULT 39.0;

-- Back-fill any rows that somehow have NULL (shouldn't happen with DEFAULT, but safe)
UPDATE res_company SET sr_exchange_rate_usd = 36.5 WHERE sr_exchange_rate_usd IS NULL;
UPDATE res_company SET sr_exchange_rate_eur = 39.0 WHERE sr_exchange_rate_eur IS NULL;

SELECT id, name, sr_exchange_rate_usd, sr_exchange_rate_eur FROM res_company;
