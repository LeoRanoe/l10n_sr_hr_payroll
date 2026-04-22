# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as dt_date

from odoo import api, fields, models
from odoo.exceptions import UserError


class SrPayrollAnnualStatementWizard(models.TransientModel):
    _name = 'sr.payroll.annual.statement.wizard'
    _description = 'SR Payroll Annual Statement Wizard'

    employee_id = fields.Many2one('hr.employee', required=True, check_company=True)
    year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    company_id = fields.Many2one('res.company', compute='_compute_company_id')

    @api.depends('employee_id')
    def _compute_company_id(self):
        for wizard in self:
            wizard.company_id = wizard.employee_id.company_id or self.env.company

    def _get_year_date_range(self):
        self.ensure_one()
        return dt_date(self.year, 1, 1), dt_date(self.year, 12, 31)

    def _get_sr_payslips(self):
        self.ensure_one()
        if self.year < 2000 or self.year > fields.Date.context_today(self).year + 1:
            raise UserError('Kies een geldig boekjaar voor de jaaropgave.')
        date_from, date_to = self._get_year_date_range()
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        return self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', sr_struct.id if sr_struct else False),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ], order='date_from, id')

    def _get_employee_address(self):
        self.ensure_one()
        employee = self.employee_id
        address_parts = [
            employee.private_street,
            employee.private_street2,
            employee.private_city,
        ]
        return ', '.join(part for part in address_parts if part)

    def _get_name_parts(self):
        self.ensure_one()
        full_name = (self.employee_id.name or '').strip()
        if not full_name:
            return '-', '-'
        name_parts = full_name.split()
        if len(name_parts) == 1:
            return name_parts[0], '-'
        return name_parts[-1], ' '.join(name_parts[:-1])

    def _get_sr_annual_statement_data(self):
        self.ensure_one()
        slips = self._get_sr_payslips()
        if not slips:
            raise UserError('Voor deze werknemer zijn geen afgeronde SR-loonstroken gevonden in het gekozen jaar.')

        exempt_codes = {'SR_KB_VRIJ', 'SR_KINDBIJ', 'SR_INPUT_VRIJ', 'SR_HK'}
        skip_codes = {'GROSS', 'NET'}
        income_map = {}
        pension_total = 0.0
        article14_rows = []
        tax_credit_rows = []
        lb_total = 0.0
        aov_total = 0.0
        net_total = 0.0

        for slip in slips:
            breakdown = slip._get_sr_artikel14_breakdown()
            net_total += breakdown.get('netto', 0.0)
            tax_rows = [
                ('art 14', 'Loonperiode', breakdown.get('lb_per_periode', 0.0), breakdown.get('aov_per_periode', 0.0)),
                ('art 17', 'Bijzondere beloningen', breakdown.get('lb_bijz', 0.0), breakdown.get('aov_bijz', 0.0)),
                ('art 17a', 'Uitkering ineens', breakdown.get('lb_17a', 0.0), breakdown.get('aov_17a', 0.0)),
                ('art 17c', 'Overwerk', breakdown.get('lb_overwerk', 0.0), breakdown.get('aov_overwerk', 0.0)),
            ]

            for article, description, loonbelasting, aov in tax_rows:
                if abs(loonbelasting) < 0.005 and abs(aov) < 0.005:
                    continue
                lb_total += loonbelasting
                aov_total += aov
                article14_rows.append({
                    'article': article,
                    'description': description,
                    'date_from': slip.date_from,
                    'date_to': slip.date_to,
                    'loonbelasting': loonbelasting,
                    'aov': aov,
                })

            if breakdown.get('heffingskorting', 0.0):
                tax_credit_rows.append({
                    'description': slip.date_to.strftime('%b %Y').upper() if slip.date_to else slip.name,
                    'amount': breakdown.get('heffingskorting', 0.0),
                })

            for line in slip.line_ids.sorted(lambda record: (record.sequence, record.code or '', record.id)):
                total = line.total or 0.0
                code = line.code or ''
                if code in skip_codes or not line.appears_on_payslip or abs(total) < 0.005:
                    continue
                if code == 'SR_PENSIOEN':
                    pension_total += abs(total)
                    continue
                if total <= 0:
                    continue
                bucket = income_map.setdefault(code, {
                    'description': (line.name or line.salary_rule_id.name or code).upper(),
                    'gross_amount': 0.0,
                    'taxable_amount': 0.0,
                })
                bucket['gross_amount'] += total
                if code not in exempt_codes:
                    bucket['taxable_amount'] += total

        surname, given_names = self._get_name_parts()
        employee = self.employee_id
        company_partner = employee.company_id.partner_id
        district = employee.private_state_id.name or employee.private_city or '-'

        income_rows = sorted(income_map.values(), key=lambda row: row['description'])
        return {
            'year': self.year,
            'surname': surname,
            'given_names': given_names,
            'employee_name': employee.name or '-',
            'address': self._get_employee_address() or '-',
            'birth_date': employee.birthday,
            'district': district,
            'job_title': employee.job_id.name or employee.job_title or '-',
            'income_rows': income_rows,
            'income_gross_total': sum(row['gross_amount'] for row in income_rows),
            'income_taxable_total': sum(row['taxable_amount'] for row in income_rows),
            'pension_total': pension_total,
            'article14_rows': article14_rows,
            'lb_total': lb_total,
            'aov_total': aov_total,
            'tax_credit_rows': tax_credit_rows,
            'tax_credit_total': sum(row['amount'] for row in tax_credit_rows),
            'net_total': net_total,
            'company_name': employee.company_id.name or '-',
            'company_address': ', '.join(part for part in [company_partner.street, company_partner.street2, company_partner.city] if part),
            'company_phone': company_partner.phone or employee.company_id.phone or '-',
        }

    def action_export_pdf(self):
        self.ensure_one()
        self._get_sr_annual_statement_data()
        return self.env.ref('l10n_sr_hr_payroll.action_report_sr_annual_statement').report_action(self, config=False)