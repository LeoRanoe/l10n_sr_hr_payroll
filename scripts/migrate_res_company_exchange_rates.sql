-- migrate_res_company_exchange_rates.sql
-- Adds per-company SR payroll columns to res_company.
-- Safe to run multiple times (IF NOT EXISTS / WHERE IS NULL).
--
-- Usage on the VM (PowerShell):
--   .\deploy_vm.ps1 -SkipUpgrade
-- Or directly via psql:
--   psql -h localhost -U openpg -d YOUR_DB_NAME -f migrate_res_company_exchange_rates.sql

-- ── Exchange rates ────────────────────────────────────────────────────────────
ALTER TABLE res_company
  ADD COLUMN IF NOT EXISTS sr_exchange_rate_usd double precision DEFAULT 36.5;

ALTER TABLE res_company
  ADD COLUMN IF NOT EXISTS sr_exchange_rate_eur double precision DEFAULT 39.0;

UPDATE res_company SET sr_exchange_rate_usd = 36.5 WHERE sr_exchange_rate_usd IS NULL;
UPDATE res_company SET sr_exchange_rate_eur = 39.0 WHERE sr_exchange_rate_eur IS NULL;

-- ── Default contract currency (Many2one → res.currency.id) ───────────────────
ALTER TABLE res_company
  ADD COLUMN IF NOT EXISTS sr_default_contract_currency_id integer;

-- Set default to SRD for rows that have no value yet
UPDATE res_company
  SET sr_default_contract_currency_id = (
    SELECT id FROM res_currency WHERE name = 'SRD' LIMIT 1
  )
  WHERE sr_default_contract_currency_id IS NULL;

-- ── Activate SRD/USD/EUR currencies ──────────────────────────────────────────
-- The module upgrade (odoo-bin -u) applies res_currency_srd_data.xml which does
-- this automatically. Run the UPDATE below only if you are skipping the upgrade.
UPDATE res_currency SET active = TRUE, symbol = 'SRD' WHERE name = 'SRD';
UPDATE res_currency SET active = TRUE WHERE name IN ('USD', 'EUR');

-- ── Summary ───────────────────────────────────────────────────────────────────
SELECT id, name, sr_exchange_rate_usd, sr_exchange_rate_eur,
       sr_default_contract_currency_id
FROM res_company;

SELECT name, symbol, active FROM res_currency WHERE name IN ('SRD','USD','EUR');
