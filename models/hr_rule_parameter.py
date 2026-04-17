# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from . import sr_artikel14_calculator as calc


class HrRuleParameter(models.Model):
    _inherit = 'hr.rule.parameter'

    sr_current_value = fields.Char(
        string='Waarde (vandaag)',
        compute='_compute_sr_current_value',
    )

    @api.depends('code', 'parameter_version_ids.date_from', 'parameter_version_ids.parameter_value')
    def _compute_sr_current_value(self):
        today = fields.Date.context_today(self)
        for parameter in self:
            if not parameter.code:
                parameter.sr_current_value = False
                continue
            value = calc.get_sr_parameter_value(
                self.env,
                parameter.code,
                today,
                default=None,
                raise_if_not_found=False,
            )
            parameter.sr_current_value = str(value) if value not in (None, False, '') else False