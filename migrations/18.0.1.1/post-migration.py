# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


SR_INPUT_XMLIDS = (
    'l10n_sr_hr_payroll.sr_input_belastbare_toelage',
    'l10n_sr_hr_payroll.sr_input_vrije_vergoeding',
    'l10n_sr_hr_payroll.sr_input_medische_vergoeding',
    'l10n_sr_hr_payroll.sr_input_inhouding',
    'l10n_sr_hr_payroll.sr_input_overwerk',
    'l10n_sr_hr_payroll.sr_input_overwerk_150',
    'l10n_sr_hr_payroll.sr_input_overwerk_200',
    'l10n_sr_hr_payroll.sr_input_vakantietoelage',
    'l10n_sr_hr_payroll.sr_input_gratificatie',
    'l10n_sr_hr_payroll.sr_input_prestatie_bonus',
    'l10n_sr_hr_payroll.sr_input_bijz_beloning',
    'l10n_sr_hr_payroll.sr_input_uitkering_ineens',
    'l10n_sr_hr_payroll.sr_input_bzv_werknemer',
    'l10n_sr_hr_payroll.sr_input_fvo_werknemer',
    'l10n_sr_hr_payroll.sr_input_vakbond',
    'l10n_sr_hr_payroll.sr_input_bzv_werkgever',
    'l10n_sr_hr_payroll.sr_input_wisselkoers',
)

SR_STRUCTURE_XMLIDS = (
    'l10n_sr_hr_payroll.sr_payroll_structure',
    'l10n_sr_hr_payroll.sr_payroll_structure_hourly',
)


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

    env = api.Environment(cr, SUPERUSER_ID, {})
    input_types = env['hr.payslip.input.type']
    for xmlid in SR_INPUT_XMLIDS:
        input_type = env.ref(xmlid, raise_if_not_found=False)
        if input_type:
            input_types |= input_type

    for xmlid in SR_STRUCTURE_XMLIDS:
        structure = env.ref(xmlid, raise_if_not_found=False)
        if structure and input_types:
            structure.input_line_type_ids = [(4, input_type_id) for input_type_id in input_types.ids]
