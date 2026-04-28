# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def _register_hook(self):
        result = super()._register_hook()

        env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        gross_formula = "result = categories['BASIC'] + result_rules['SR_ALW']['total']"
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