"""Run this file inside `odoo-bin shell` after go-live.

Example:
    exec(open(r"c:\\Program Files\\Odoo 18.0e.20260407\\sessions\\addons\\18.0\\l10n_sr_hr_payroll\\scripts\\post_deployment_verify.py").read())
"""

from datetime import date


if 'env' not in globals():
    raise RuntimeError('Run this verification inside `odoo-bin shell`, where `env` is available.')


PARAM_KEYS = {
    'sr_payroll.belastingvrij_jaar': 0.0,
    'sr_payroll.heffingskorting': 750.0,
    'sr_payroll.akb_per_kind': 250.0,
    'sr_payroll.akb_max_bedrag': 1000.0,
    'sr_payroll.exchange_rate_usd': 36.5,
    'sr_payroll.exchange_rate_eur': 39.0,
}

RULE_VALUE_XMLIDS = {
    'sr_param_belastingvrij_jaar_2026': 0.0,
    'sr_param_heffingskorting_2026': 750.0,
    'sr_param_kindbij_max_kind_maand_2026': 250.0,
    'sr_param_kindbij_max_maand_2026': 1000.0,
    'sr_param_aov_tarief_2026': 0.04,
    'sr_param_aov_franchise_maand_2026': 400.0,
}


def _to_float(value):
    if value in (None, False, ''):
        return None
    return float(value)


def _print_header(title):
    print('\n' + '=' * 78)
    print(title)
    print('=' * 78)


params = env['ir.config_parameter'].sudo()

_print_header('SR Payroll Go-Live Verification')
print('Database:', env.cr.dbname)
print('Company:', env.company.name)
print('Check date:', date.today())

_print_header('Config Parameters')
for key, expected in PARAM_KEYS.items():
    actual = _to_float(params.get_param(key))
    status = 'OK' if actual == expected else 'CHECK'
    print(f'[{status}] {key}: actual={actual} expected={expected}')

_print_header('2026 Rule Parameter Values')
for xmlid, expected in RULE_VALUE_XMLIDS.items():
    record = env.ref(f'l10n_sr_hr_payroll.{xmlid}', raise_if_not_found=False)
    if not record:
        print(f'[MISSING] {xmlid}')
        continue
    actual = _to_float(record.parameter_value)
    status = 'OK' if actual == expected and record.date_from == date(2026, 1, 1) else 'CHECK'
    print(f'[{status}] {xmlid}: date_from={record.date_from} actual={actual} expected={expected}')

_print_header('Schema Sanity')
env.cr.execute(
    """
    SELECT indexname
      FROM pg_indexes
     WHERE schemaname = 'public'
       AND indexname IN (
           'hr_payslip_sr_struct_state_idx',
           'hr_payslip_line_slip_code_idx',
           'hr_payslip_input_generated_idx',
           'hr_work_entry_contract_state_dates_idx'
       )
     ORDER BY indexname
    """
)
found_indexes = [row[0] for row in env.cr.fetchall()]
print('Indexes:', found_indexes)

env.cr.execute(
    """
    SELECT COUNT(*)
      FROM hr_rule_parameter_value v
      JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id
     WHERE p.code IN (
         'SR_BELASTINGVRIJ_JAAR',
         'SR_HEFFINGSKORTING',
         'SR_KINDBIJ_MAX_KIND_MAAND',
         'SR_KINDBIJ_MAX_MAAND',
         'SR_AOV_TARIEF',
         'SR_AOV_FRANCHISE_MAAND'
     )
       AND v.date_from = %s
    """,
    [date(2026, 1, 1)],
)
print('2026 fiscal values found:', env.cr.fetchone()[0])

print('\nVerification finished. Review any [CHECK] or [MISSING] lines before go-live.')