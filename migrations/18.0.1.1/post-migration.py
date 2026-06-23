# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Move old 2026 default config overrides to the corrected legal defaults."""
    replacements = (
        ('sr_payroll.belastingvrij_jaar', '108000.0', ('0', '0.0', '0.00')),
        ('sr_payroll.heffingskorting', '0.0', ('750', '750.0', '750.00')),
        ('sr_payroll.aov_franchise_maand', '0.0', ('400', '400.0', '400.00')),
    )
    for key, new_value, old_values in replacements:
        placeholders = ','.join(['%s'] * len(old_values))
        cr.execute(
            f"""
            UPDATE ir_config_parameter
               SET value = %s
             WHERE key = %s
               AND value IN ({placeholders})
            """,
            (new_value, key, *old_values),
        )
