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
            parameter.sr_current_value = str(value) if not calc.is_missing_parameter_value(value) else False

    def _sr_sync_current_config_override(self):
        if self.env.context.get('install_mode'):
            return

        today = fields.Date.context_today(self)
        params = self.env['ir.config_parameter'].sudo()
        cache_invalidated = False

        for parameter in self:
            config_key = calc.get_config_parameter_key(parameter.code)
            if not config_key:
                continue

            active_versions = parameter.parameter_version_ids.filtered(
                lambda version: version.date_from and version.date_from <= today
            ).sorted(lambda version: version.date_from)

            if active_versions:
                value = active_versions[-1].parameter_value
            else:
                value = calc.get_config_parameter_default(parameter.code)

            params.set_param(config_key, value if value not in (None, False) else '')
            cache_invalidated = True

        if cache_invalidated:
            self.env.registry.clear_cache()


class HrRuleParameterValue(models.Model):
    _inherit = 'hr.rule.parameter.value'

    def _sr_sync_parent_parameters(self, extra_parameters=None):
        parameters = self.mapped('rule_parameter_id')
        if extra_parameters:
            parameters |= extra_parameters
        parameters._sr_sync_current_config_override()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sr_sync_parent_parameters()
        return records

    def write(self, vals):
        parameters = self.mapped('rule_parameter_id')
        result = super().write(vals)
        self._sr_sync_parent_parameters(extra_parameters=parameters)
        return result

    def unlink(self):
        parameters = self.mapped('rule_parameter_id')
        result = super().unlink()
        parameters._sr_sync_current_config_override()
        return result