# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import http
from odoo.http import request


class SrPayrollHelpController(http.Controller):
    """Controller voor de Suriname Payroll Help & Documentatie pagina."""

    @http.route('/sr_payroll/help', type='http', auth='user', csrf=False)
    def sr_help_page(self, **kwargs):
        """Render de help & documentatie pagina."""
        # Haal actuele parameterwaarden op voor weergave
        env = request.env
        today = date.today()

        params = {}
        param_codes = [
            ('SR_BELASTINGVRIJ_JAAR', 'Belastingvrije voet (Art. 13)'),
            ('SR_FORFAITAIRE_PCT', 'Forfaitaire aftrek %'),
            ('SR_FORFAITAIRE_MAX_JAAR', 'Forfaitaire aftrek max'),
            ('SR_SCHIJF_1_GRENS', 'Schijf 1 grens'),
            ('SR_SCHIJF_2_GRENS', 'Schijf 2 grens'),
            ('SR_SCHIJF_3_GRENS', 'Schijf 3 grens'),
            ('SR_TARIEF_1', 'Tarief 1'),
            ('SR_TARIEF_2', 'Tarief 2'),
            ('SR_TARIEF_3', 'Tarief 3'),
            ('SR_TARIEF_4', 'Tarief 4'),
            ('SR_HEFFINGSKORTING_MAAND', 'Heffingskorting per maand'),
            ('SR_AOV_TARIEF', 'AOV tarief'),
            ('SR_AOV_FRANCHISE_MAAND', 'AOV franchise per maand'),
            ('SR_OWK_SCHIJF_1_GRENS', 'Overwerk schijf 1'),
            ('SR_OWK_SCHIJF_2_GRENS', 'Overwerk schijf 2'),
            ('SR_OWK_TARIEF_1', 'Overwerk tarief 1'),
            ('SR_OWK_TARIEF_2', 'Overwerk tarief 2'),
            ('SR_OWK_TARIEF_3', 'Overwerk tarief 3'),
            ('SR_BIJZ_VRIJSTELLING_MAX', 'Bijz. vrijstelling max'),
            ('SR_KINDBIJ_MAX_KIND_MAAND', 'Kinderbijslag max/kind'),
            ('SR_KINDBIJ_MAX_MAAND', 'Kinderbijslag max/maand'),
        ]
        RuleParam = env['hr.rule.parameter'].sudo()
        for code, label in param_codes:
            try:
                val = RuleParam._get_parameter_from_code(code, today, raise_if_not_found=True)
                params[code] = {'label': label, 'value': val}
            except Exception:
                params[code] = {'label': label, 'value': 'N/B'}

        return request.render('l10n_sr_hr_payroll.sr_help_template', {
            'params': params,
        })
