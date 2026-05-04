# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from datetime import date
from decimal import Decimal

from odoo import SUPERUSER_ID, http
from odoo.exceptions import AccessError
from odoo.http import request

from ..models import sr_artikel14_calculator as calc


_LB_PARAM_RE = re.compile(r'^SR_(SCHIJF_(\d+)_GRENS|TARIEF_(\d+))$')
_PERCENT_PARAM_HINTS = ('TARIEF', '_PCT')
_CURRENCY_PARAM_HINTS = ('GRENS', 'MAX', 'VRIJ', 'FRANCHISE')


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


def _coerce_float(value):
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_param_value(code, value):
    if value is None:
        return 'N/B'

    numeric_value = _coerce_float(value)
    if numeric_value is None:
        return str(value)

    if code and any(token in code for token in _PERCENT_PARAM_HINTS):
        return f'{numeric_value * 100:.2f}%'

    if code and any(token in code for token in _CURRENCY_PARAM_HINTS):
        return f'SRD {numeric_value:,.2f}'

    if numeric_value.is_integer():
        return f'{numeric_value:,.0f}'

    return f'{numeric_value:,.2f}'


class SrPayrollHelpController(http.Controller):
    """Controller voor de Suriname Payroll Help & Documentatie pagina."""

    @http.route('/sr_payroll/help', type='http', auth='user', csrf=False)
    def sr_help_page(self, **kwargs):
        """Render de help & documentatie pagina."""
        user = request.env.user
        allowed_groups = (
            'hr_payroll.group_hr_payroll_user',
            'hr_payroll.group_hr_payroll_manager',
            'l10n_sr_hr_payroll.group_sr_payroll_accountant_export',
            'base.group_system',
        )
        if not any(user.has_group(group) for group in allowed_groups):
            raise AccessError('Je hebt geen toegang tot deze SR payroll help-pagina.')

        # Haal actuele parameterwaarden op voor weergave
        env = request.env(user=SUPERUSER_ID)
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
        RuleParam = env['hr.rule.parameter']
        extra_lb_codes = sorted(
            {
                param.code for param in RuleParam.search([('code', 'like', 'SR_%')])
                if _LB_PARAM_RE.match(param.code)
            } - {code for code, _label in param_codes},
            key=_lb_param_sort_key,
        )
        param_codes.extend((code, _lb_param_label(code)) for code in extra_lb_codes)
        for code, label in param_codes:
            val = calc.get_sr_parameter_value(
                env, code, today, default=None, raise_if_not_found=False,
            )
            if val is None:
                params[code] = {
                    'label': label,
                    'value': 'N/B',
                    'display_value': 'N/B',
                }
            else:
                params[code] = {
                    'label': label,
                    'value': val,
                    'display_value': _format_param_value(code, val),
                }

        try:
            lb_calc_params = calc.fetch_params_from_rule_parameter(env, today)
            lb_brackets = lb_calc_params.get('brackets', [])
        except Exception:
            lb_brackets = []

        return request.render('l10n_sr_hr_payroll.sr_help_template', {
            'params': params,
            'v': {code: params[code]['value'] for code in params if params[code]['value'] != 'N/B'},
            'lb_brackets': lb_brackets,
            'lb_rate_summary': ' / '.join(f"{row['rate'] * 100:.0f}%" for row in lb_brackets),
            'param_count': len(params),
            'bracket_count': len(lb_brackets),
            'today_display': today.strftime('%d-%m-%Y'),
        })
