# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api, models


_SR_RULE_SYNC_FIELDS = (
    'name',
    'sequence',
    'code',
    'category_id',
    'active',
    'appears_on_payslip',
    'appears_on_employee_cost_dashboard',
    'appears_on_payroll_report',
    'condition_select',
    'condition_range',
    'condition_range_min',
    'condition_range_max',
    'condition_other_input_id',
    'condition_python',
    'amount_select',
    'amount_fix',
    'amount_percentage',
    'amount_percentage_base',
    'amount_other_input_id',
    'amount_python_compute',
    'quantity',
    'partner_id',
    'note',
)


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def _register_hook(self):
        result = super()._register_hook()

        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        self._sr_sync_hourly_structure_rules(env)

        gross_formula = "result = categories['BASIC'] + categories['ALW'] + categories['SR_GRD']"
        net_formula = (
            "result = categories['BASIC'] + categories['ALW'] + categories['DED'] + "
            "categories['SR_VRIJ'] - (result_rules['SR_HK']['total'] if 'SR_HK' in result_rules else 0.0)"
        )
        structure_xmlids = [
            'l10n_sr_hr_payroll.sr_payroll_structure',
            'l10n_sr_hr_payroll.sr_payroll_structure_hourly',
        ]

        for xmlid in structure_xmlids:
            structure = env.ref(xmlid, raise_if_not_found=False)
            if not structure:
                continue

            sr_gross_rule = env.ref('l10n_sr_hr_payroll.sr_rule_gross', raise_if_not_found=False)
            duplicate_gross_rules = structure.rule_ids.filtered(
                lambda rule: rule.code == 'GROSS' and rule.id != (sr_gross_rule.id if sr_gross_rule else 0)
            )
            mismatched_rules = duplicate_gross_rules.filtered(
                lambda rule: (rule.amount_python_compute or '').strip() != gross_formula
            )
            if mismatched_rules:
                mismatched_rules.write({'amount_python_compute': gross_formula})

            sr_net_rule = env.ref('l10n_sr_hr_payroll.sr_rule_net', raise_if_not_found=False)
            duplicate_net_rules = structure.rule_ids.filtered(
                lambda rule: rule.code == 'NET' and rule.id != (sr_net_rule.id if sr_net_rule else 0)
            )
            mismatched_net_rules = duplicate_net_rules.filtered(
                lambda rule: (rule.amount_python_compute or '').strip() != net_formula
            )
            if mismatched_net_rules:
                mismatched_net_rules.write({'amount_python_compute': net_formula})

        return result

    def _sr_get_rule_sync_values(self, source_rule, target_structure):
        values = {'struct_id': target_structure.id}
        for field_name in _SR_RULE_SYNC_FIELDS:
            field = source_rule._fields[field_name]
            value = source_rule[field_name]
            if field.type == 'many2one':
                values[field_name] = value.id if value else False
            else:
                values[field_name] = value
        return values

    def _sr_get_rule_sync_diff(self, target_rule, values):
        diff = {}
        for field_name, value in values.items():
            field = target_rule._fields[field_name]
            current_value = target_rule[field_name]
            if field.type == 'many2one':
                current_value = current_value.id if current_value else False
            if current_value != value:
                diff[field_name] = value
        return diff

    def _sr_sync_hourly_structure_rules(self, env):
        normal_structure = env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        hourly_structure = env.ref('l10n_sr_hr_payroll.sr_payroll_structure_hourly', raise_if_not_found=False)
        if not normal_structure or not hourly_structure:
            return

        sr_rule_model_data = env['ir.model.data'].search([
            ('module', '=', 'l10n_sr_hr_payroll'),
            ('model', '=', 'hr.salary.rule'),
        ])
        sr_rule_ids = set(sr_rule_model_data.mapped('res_id'))
        source_rules = normal_structure.rule_ids.filtered(lambda rule: rule.id in sr_rule_ids)
        target_rules_by_key = {
            (rule.code, rule.sequence): rule
            for rule in hourly_structure.rule_ids
        }

        for source_rule in source_rules.sorted(lambda rule: (rule.sequence, rule.code, rule.id)):
            values = self._sr_get_rule_sync_values(source_rule, hourly_structure)
            key = (source_rule.code, source_rule.sequence)
            target_rule = target_rules_by_key.get(key)
            if target_rule:
                diff = self._sr_get_rule_sync_diff(target_rule, values)
                if diff:
                    target_rule.write(diff)
            else:
                target_rules_by_key[key] = source_rule.copy(values)

    @api.model
    def _sr_sync_hourly_structure_rules_from_xml(self):
        self._sr_sync_hourly_structure_rules(self.env)
