# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    sr_has_sr_payslips = fields.Boolean(
        string='Bevat SR-loonstroken',
        compute='_compute_sr_has_sr_payslips',
    )

    @api.depends('slip_ids', 'slip_ids.struct_id', 'slip_ids.state')
    def _compute_sr_has_sr_payslips(self):
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        for payslip_run in self:
            payslip_run.sr_has_sr_payslips = bool(
                sr_struct and payslip_run.slip_ids.filtered(lambda slip: slip.struct_id == sr_struct)
            )

    def _sr_get_tax_overview_slips(self):
        self.ensure_one()
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        return self.slip_ids.filtered(
            lambda slip: slip.struct_id == sr_struct and slip.state in ('done', 'paid')
        ).sorted(lambda slip: (
            slip.employee_id.department_id.name or '',
            slip.employee_id.name or '',
            slip.date_from or fields.Date.today(),
            slip.id,
        ))

    def action_print_sr_tax_overview(self):
        self.ensure_one()
        slips = self._sr_get_tax_overview_slips()
        if not slips:
            raise UserError(
                'Er zijn geen afgeronde SR-loonstroken in deze loonrun om een belastingoverzicht te exporteren.'
            )
        return self.env.ref('l10n_sr_hr_payroll.action_report_sr_tax_overview_period').report_action(self, config=False)

    def action_open_sr_tax_report_export_wizard(self):
        """Open de CSV-exportwizard met de loonrunperiode als standaardfilter."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exporteer SR Fiscaal Overzicht',
            'res_model': 'sr.payroll.tax.report.export.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_company_id': self.company_id.id,
                'default_date_from': self.date_start,
                'default_date_to': self.date_end,
            },
        }

    def action_open_sr_tax_report(self):
        """Open het SR Fiscaal Belastingoverzicht gefilterd op deze loonrun."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'SR Fiscaal Overzicht',
            'res_model': 'hr.payroll.tax.report',
            'view_mode': 'list,pivot,form',
            'domain': [('payslip_run_id', '=', self.id)],
            'context': {
                'search_default_group_by_department': 1,
            },
        }

    # ── Bedrijfs Belastingoverzicht Periode ────────────────────────────────

    _SR_OVERVIEW_KEYS = [
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
        'amount_belastingvrij_periode_srd',
        'amount_netto_srd',
        'amount_netto_bronvaluta',
        'amount_overwerk_150_srd',
        'amount_overwerk_200_srd',
    ]

    def _sr_get_company_period_overview_data(self):
        """
        Bereidt gestructureerde gegevens voor de Bedrijfs Belastingoverzicht Periode PDF.

        Haalt hr.payroll.tax.report-records op gefilterd op deze loonrun,
        groepeert per afdeling en berekent subtotalen + totaalbedrijf.

        :returns: dict met run-info, dept_groups (per afdeling: employees + totals)
                  en grand_totals, geschikt voor QWeb-rendering.
        """
        self.ensure_one()
        self.env.flush_all()
        records = self.env['hr.payroll.tax.report'].search(
            [('payslip_run_id', '=', self.id)],
            order='department_name, employee_name',
        )
        if not records:
            raise UserError(
                'Geen afgeronde SR-loonstroken gevonden voor dit bedrijfsoverzicht. '
                'Controleer of de loonstroken zijn bevestigd (done/paid).'
            )

        keys = self._SR_OVERVIEW_KEYS
        zero = {k: 0.0 for k in keys}

        dept_groups = {}
        for rec in records:
            dept_key = rec.department_name or '(Geen afdeling)'
            if dept_key not in dept_groups:
                dept_groups[dept_key] = {
                    'dept_name': dept_key,
                    'employees': [],
                    'totals': dict(zero),
                }
            emp = {
                'employee_name': rec.employee_name or '-',
                'employee_id_no': rec.employee_identification_id or '-',
            }
            for k in keys:
                emp[k] = getattr(rec, k, 0.0) or 0.0
                dept_groups[dept_key]['totals'][k] += emp[k]
            dept_groups[dept_key]['employees'].append(emp)

        grand_totals = dict(zero)
        for dg in dept_groups.values():
            for k in keys:
                grand_totals[k] += dg['totals'][k]

        company = self.company_id or self.env.company
        partner = company.partner_id
        addr_parts = [p for p in [partner.street, partner.city, partner.country_id.name] if p]

        return {
            'run_name': self.name or '-',
            'date_from': self.date_start,
            'date_to': self.date_end,
            'company_name': company.name or '-',
            'company_address': ', '.join(addr_parts),
            'company_phone': partner.phone or company.phone or '-',
            'company_vat': company.vat or '-',
            'dept_groups': list(dept_groups.values()),
            'grand_totals': grand_totals,
            'generated_on': fields.Date.context_today(self),
            'employee_count': len(records),
        }

    def action_print_sr_company_period_overview(self):
        """Print het Bedrijfs Belastingoverzicht Periode als PDF."""
        self.ensure_one()
        slips = self._sr_get_tax_overview_slips()
        if not slips:
            raise UserError(
                'Er zijn geen afgeronde SR-loonstroken in deze loonrun om een bedrijfsoverzicht te exporteren.'
            )
        return self.env.ref(
            'l10n_sr_hr_payroll.action_report_sr_company_period_overview'
        ).report_action(self, config=False)