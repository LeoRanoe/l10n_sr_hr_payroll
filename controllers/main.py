# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from datetime import date

from odoo import http
from odoo.http import request

from ..models import sr_artikel14_calculator as calc


_LB_PARAM_RE = re.compile(r'^SR_(SCHIJF_(\d+)_GRENS|TARIEF_(\d+))$')


def _lb_param_sort_key(code):
    match = _LB_PARAM_RE.match(code or '')
    if not match:
        return (99, code or '')
    if match.group(2):
        return (0, int(match.group(2)))
    return (1, int(match.group(3)))


def _lb_param_label(code):
    match = _LB_PARAM_RE.match(code or '')
    if not match:
        return code
    if match.group(2):
        return f'Schijf {int(match.group(2))} grens'
    return f'Tarief {int(match.group(3))}'


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
        extra_lb_codes = sorted(
            {
                param.code for param in RuleParam.search([('code', 'like', 'SR_%')])
                if _LB_PARAM_RE.match(param.code)
            } - {code for code, _label in param_codes},
            key=_lb_param_sort_key,
        )
        param_codes.extend((code, _lb_param_label(code)) for code in extra_lb_codes)
        for code, label in param_codes:
            try:
                val = RuleParam._get_parameter_from_code(code, today, raise_if_not_found=True)
                params[code] = {'label': label, 'value': val}
            except Exception:
                params[code] = {'label': label, 'value': 'N/B'}

        lb_calc_params = calc.fetch_params_from_rule_parameter(env, today)
        lb_brackets = lb_calc_params.get('tax_brackets', [])

        return request.render('l10n_sr_hr_payroll.sr_help_template', {
            'params': params,
            'v': {code: params[code]['value'] for code in params if params[code]['value'] != 'N/B'},
            'lb_brackets': lb_brackets,
            'lb_rate_summary': ' / '.join(f"{row['rate'] * 100:.0f}%" for row in lb_brackets),
        })
