# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""SR Bedrijfs Jaaroverzicht — wizard voor de jaarlijkse belastingrapportage per bedrijf."""

from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


_SR_YEAR_KEYS = [
    'amount_bruto_srd',
    'amount_bijz_bruto_srd',
    'amount_uitk_ineens_srd',
    'amount_lb_art14_srd',
    'amount_lb_bijz_srd',
    'amount_lb_17a_srd',
    'amount_lb_overwerk_srd',
    'amount_lb_srd',
    'amount_aov_art14_srd',
    'amount_aov_bijz_srd',
    'amount_aov_17a_srd',
    'amount_aov_overwerk_srd',
    'amount_aov_srd',
    'amount_heffingskorting_srd',
    'amount_pensioen_srd',
    'amount_akb_srd',
    'amount_netto_srd',
    'amount_overwerk_150_srd',
    'amount_overwerk_200_srd',
]


class SrPayrollCompanyYearWizard(models.TransientModel):
    _name = 'sr.payroll.company.year.wizard'
    _description = 'SR Bedrijfs Jaaroverzicht Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Bedrijf',
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Integer(
        string='Boekjaar',
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )

    @api.constrains('year')
    def _check_year(self):
        current_year = fields.Date.context_today(self).year
        for rec in self:
            if not (2000 <= rec.year <= current_year + 1):
                raise UserError(
                    f'Kies een geldig boekjaar (2000 – {current_year + 1}).'
                )

    def _get_company_year_overview_data(self):
        """
        Bereidt gestructureerde gegevens voor het Bedrijfs Jaaroverzicht PDF.

        Haalt alle bevestigde SR-loonstrookrecords op voor dit bedrijf en jaar,
        groepeert per afdeling, accumuleert jaarlijkse totalen per werknemer
        en berekent afdelings- en bedrijfstotalen.

        :returns: dict met jaar-info, dept_groups en grand_totals.
        """
        self.ensure_one()
        self.env.flush_all()

        date_from = date(self.year, 1, 1)
        date_to = date(self.year, 12, 31)

        records = self.env['hr.payroll.tax.report'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ], order='department_name, employee_name, date_from')

        if not records:
            raise UserError(
                f'Geen bevestigde SR-loonstroken gevonden voor {self.company_id.name} '
                f'in het boekjaar {self.year}. '
                'Controleer of de loonstroken zijn bevestigd (done/paid).'
            )

        keys = _SR_YEAR_KEYS
        zero = {k: 0.0 for k in keys}

        # Accumulate per (dept, employee) to get annual totals
        dept_groups = {}
        for rec in records:
            dept_key = rec.department_name or '(Geen afdeling)'
            emp_key = (dept_key, rec.employee_id.id or rec.employee_name or '')

            if dept_key not in dept_groups:
                dept_groups[dept_key] = {
                    'dept_name': dept_key,
                    'employees': {},
                    'totals': dict(zero),
                }

            if emp_key not in dept_groups[dept_key]['employees']:
                dept_groups[dept_key]['employees'][emp_key] = {
                    'employee_name': rec.employee_name or '-',
                    'employee_id_no': rec.employee_identification_id or '-',
                    'slip_count': 0,
                    **dict(zero),
                }

            emp_entry = dept_groups[dept_key]['employees'][emp_key]
            emp_entry['slip_count'] += 1
            for k in keys:
                val = getattr(rec, k, 0.0) or 0.0
                emp_entry[k] += val
                dept_groups[dept_key]['totals'][k] += val

        # Flatten employee dicts to sorted lists
        for dg in dept_groups.values():
            dg['employees'] = sorted(
                dg['employees'].values(),
                key=lambda e: e['employee_name'],
            )

        grand_totals = dict(zero)
        total_employees = 0
        for dg in dept_groups.values():
            total_employees += len(dg['employees'])
            for k in keys:
                grand_totals[k] += dg['totals'][k]

        company = self.company_id
        partner = company.partner_id
        addr_parts = [p for p in [partner.street, partner.city, partner.country_id.name] if p]

        return {
            'year': self.year,
            'company_name': company.name or '-',
            'company_address': ', '.join(addr_parts),
            'company_phone': partner.phone or company.phone or '-',
            'company_vat': company.vat or '-',
            'dept_groups': list(dept_groups.values()),
            'grand_totals': grand_totals,
            'generated_on': fields.Date.context_today(self),
            'employee_count': total_employees,
            'slip_count': len(records),
        }

    def action_export_pdf(self):
        """Genereer het Bedrijfs Jaaroverzicht als PDF en stuur naar browser."""
        self.ensure_one()
        return self.env.ref(
            'l10n_sr_hr_payroll.action_report_sr_company_year_overview'
        ).report_action(self, config=False)
