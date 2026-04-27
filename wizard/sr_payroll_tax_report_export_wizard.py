# Part of Odoo. See LICENSE file for full copyright and licensing details.

from base64 import b64encode
import csv
from datetime import date as dt_date
from io import StringIO
import re

from odoo import fields, models
from odoo.exceptions import UserError


class SrPayrollTaxReportExportWizard(models.TransientModel):
    _name = 'sr.payroll.tax.report.export.wizard'
    _description = 'SR Payroll Tax Report Export Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Bedrijf',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Van',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    )
    date_to = fields.Date(
        string='T/m',
        required=True,
        default=fields.Date.context_today,
    )
    row_count = fields.Integer(string='Aantal regels', readonly=True)
    export_file = fields.Binary(string='CSV Bestand', readonly=True, attachment=False)
    export_filename = fields.Char(string='Bestandsnaam', readonly=True)

    def _get_export_rows(self):
        self.ensure_one()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError('De begindatum mag niet later zijn dan de einddatum.')
        self.env.flush_all()
        domain = [('company_id', '=', self.company_id.id)]
        if self.date_from:
            domain.append(('date_from', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_to', '<=', self.date_to))
        return self.env['hr.payroll.tax.report'].search(
            domain,
            order='date_from, department_name, employee_name, id',
        )

    def _get_export_filename(self):
        self.ensure_one()
        company_slug = re.sub(r'[^0-9A-Za-z]+', '_', (self.company_id.name or 'bedrijf')).strip('_').lower()
        return f'sr_fiscaal_overzicht_{company_slug}_{self.date_from}_{self.date_to}.csv'

    def _build_csv_payload(self, rows):
        state_labels = dict(self.env['hr.payroll.tax.report']._fields['payslip_state'].selection)
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'Periode van',
            'Periode t/m',
            'Afdeling',
            'Werknemer',
            'ID-nummer',
            'Contractvaluta',
            'Wisselkoers',
            'Bruto loon (SRD)',
            'Overwerk 150% (SRD)',
            'Overwerk 200% (SRD)',
            'AKB / Kinderbijslag (SRD)',
            'AOV inhouding (SRD)',
            'Belastingvrije voet/periode (SRD)',
            'Ingehouden LB (SRD)',
            'Netto loon (SRD)',
            'Netto loon (Bronvaluta)',
            'Status loonstrook',
        ])
        for row in rows:
            writer.writerow([
                fields.Date.to_string(row.date_from) if row.date_from else '',
                fields.Date.to_string(row.date_to) if row.date_to else '',
                row.department_name or '',
                row.employee_name or '',
                row.employee_identification_id or '',
                row.contract_currency_id.name or '',
                f'{row.exchange_rate or 0.0:.4f}',
                f'{row.amount_bruto_srd or 0.0:.2f}',
                f'{row.amount_overwerk_150_srd or 0.0:.2f}',
                f'{row.amount_overwerk_200_srd or 0.0:.2f}',
                f'{row.amount_akb_srd or 0.0:.2f}',
                f'{row.amount_aov_srd or 0.0:.2f}',
                f'{row.amount_belastingvrij_periode_srd or 0.0:.2f}',
                f'{row.amount_lb_srd or 0.0:.2f}',
                f'{row.amount_netto_srd or 0.0:.2f}',
                f'{row.amount_netto_bronvaluta or 0.0:.2f}',
                state_labels.get(row.payslip_state, row.payslip_state or ''),
            ])
        return buffer.getvalue().encode('utf-8-sig')

    def action_export_csv(self):
        self.ensure_one()
        rows = self._get_export_rows()
        if not rows:
            raise UserError('Er zijn geen fiscale overzichtsregels gevonden voor de gekozen filters.')
        payload = self._build_csv_payload(rows)
        self.write({
            'row_count': len(rows),
            'export_filename': self._get_export_filename(),
            'export_file': b64encode(payload),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content?model=%s&id=%s&field=export_file&download=true&filename_field=export_filename'
                % (self._name, self.id)
            ),
            'target': 'self',
        }