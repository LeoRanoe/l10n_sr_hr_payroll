# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Verzamelloonstaat Wizard — Belastingdienst Suriname
====================================================
Genereert de jaarlijkse Verzamelloonstaat CSV conform het officiële formaat
van de Belastingdienst Suriname (portaal.belastingdienst.sr).

Vereisten 2025/2026:
- CRIBNR moet NUMERIEK zijn (gewijzigd per 2025, niet langer tekst)
- Indientermijn: uiterlijk 31 januari van het volgend jaar
- Upload via: portaal.belastingdienst.sr → Aangifte → Verzamelloonstaat
"""

from base64 import b64encode
import csv
from datetime import date as dt_date
from io import StringIO
import re

from odoo import api, fields, models
from odoo.exceptions import UserError


class SrPayrollVerzamelloonstaat(models.TransientModel):
    _name = 'sr.payroll.verzamelloonstaat.wizard'
    _description = 'SR Verzamelloonstaat Export Wizard (Belastingdienst Suriname)'

    company_id = fields.Many2one(
        'res.company',
        string='Bedrijf',
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Integer(
        string='Boekjaar',
        required=True,
        default=lambda self: fields.Date.context_today(self).year - 1,
        help='Het kalenderjaar waarover de verzamelloonstaat wordt ingediend.',
    )
    row_count = fields.Integer(string='Aantal werknemers', readonly=True)
    export_file = fields.Binary(string='CSV Bestand', readonly=True, attachment=False)
    export_filename = fields.Char(string='Bestandsnaam', readonly=True)
    warning_message = fields.Char(string='Waarschuwing', readonly=True)

    @api.constrains('year')
    def _check_year(self):
        current_year = fields.Date.context_today(self).year
        for rec in self:
            if not (2000 <= rec.year <= current_year + 1):
                raise UserError(f'Kies een geldig boekjaar (2000 – {current_year + 1}).')

    def _get_annual_records(self):
        self.ensure_one()
        self.env.flush_all()
        date_from = dt_date(self.year, 1, 1)
        date_to = dt_date(self.year, 12, 31)
        return self.env['hr.payroll.tax.report'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('payslip_state', 'in', ['done', 'paid']),
        ], order='employee_name, date_from')

    def _get_employee_name_parts(self, full_name):
        parts = (full_name or '').strip().split()
        if not parts:
            return '-', '-'
        return parts[-1], ' '.join(parts[:-1]) if len(parts) > 1 else '-'

    def _aggregate_by_employee(self, records):
        """Aggregeer loonstrookrecords per werknemer tot jaarlijkse totalen."""
        emp_map = {}
        amount_keys = [
            'amount_bruto_srd',
            'amount_bijz_bruto_srd',
            'amount_uitk_ineens_srd',
            'amount_overwerk_150_srd',
            'amount_overwerk_200_srd',
            'amount_akb_srd',
            'amount_belastingvrij_periode_srd',
            'amount_aov_art14_srd',
            'amount_aov_bijz_srd',
            'amount_aov_17a_srd',
            'amount_aov_overwerk_srd',
            'amount_aov_srd',
            'amount_lb_art14_srd',
            'amount_lb_bijz_srd',
            'amount_lb_17a_srd',
            'amount_lb_overwerk_srd',
            'amount_lb_srd',
            'amount_netto_srd',
        ]
        for rec in records:
            emp_id = rec.employee_id.id or rec.employee_name
            if emp_id not in emp_map:
                surname, given_names = self._get_employee_name_parts(rec.employee_name)
                emp = rec.employee_id
                address_parts = [emp.private_street, emp.private_city] if emp else []
                loontijdvak_from = rec.date_from
                emp_map[emp_id] = {
                    'employee_name': rec.employee_name or '-',
                    'cribnr': rec.employee_identification_id or '',
                    'surname': surname,
                    'given_names': given_names,
                    'address': ', '.join(p for p in address_parts if p) or '-',
                    'loontijdvak_from': loontijdvak_from,
                    'loontijdvak_to': rec.date_to,
                    **{k: 0.0 for k in amount_keys},
                }
            entry = emp_map[emp_id]
            # Extend the loontijdvak to cover the full year range
            if rec.date_from and rec.date_from < entry['loontijdvak_from']:
                entry['loontijdvak_from'] = rec.date_from
            if rec.date_to and rec.date_to > entry['loontijdvak_to']:
                entry['loontijdvak_to'] = rec.date_to
            for k in amount_keys:
                entry[k] += getattr(rec, k, 0.0) or 0.0
        return list(emp_map.values())

    def _build_csv_payload(self, employees):
        """
        Bouw de CSV conform het Belastingdienst Suriname Verzamelloonstaat formaat.

        Kolom CRIBNR moet numeriek zijn (vereiste per 2025).
        Scheidingsteken: puntkomma (;) conform Belastingdienst template.
        """
        buffer = StringIO()
        # Belastingdienst Suriname gebruikt puntkomma als scheidingsteken
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([
            'CRIBNR',
            'Achternaam',
            'Voornamen',
            'Adres',
            'Loontijdvak Van',
            'Loontijdvak Tot',
            'Bruto regulier loon (Art. 14)',
            'Bruto bijzondere beloningen (Art. 17)',
            'Bruto uitkering ineens (Art. 17a)',
            'Overwerk 150% Bruto',
            'Overwerk 200% Bruto',
            'Kinderbijslag (Totaal)',
            'Belastingvrije Voet Jaar',
            'AOV premie regulier loon (Art. 14)',
            'AOV premie bijzondere beloningen (Art. 17)',
            'AOV premie uitkering ineens (Art. 17a)',
            'AOV premie overwerk (Art. 17c)',
            'AOV Totaal',
            'LB regulier loon (Art. 14)',
            'LB bijzondere beloningen (Art. 17)',
            'LB uitkering ineens (Art. 17a)',
            'LB overwerk (Art. 17c)',
            'LB Totaal',
            'Netto Loon',
        ])
        for emp in sorted(employees, key=lambda e: e['employee_name']):
            # CRIBNR moet numeriek zijn per Belastingdienst vereiste 2025+
            cribnr_raw = (emp['cribnr'] or '').strip()
            cribnr_numeric = re.sub(r'\D', '', cribnr_raw)

            loontijdvak_from = emp['loontijdvak_from']
            loontijdvak_to = emp['loontijdvak_to']

            writer.writerow([
                cribnr_numeric,
                emp['surname'],
                emp['given_names'],
                emp['address'],
                fields.Date.to_string(loontijdvak_from) if loontijdvak_from else '',
                fields.Date.to_string(loontijdvak_to) if loontijdvak_to else '',
                f"{emp['amount_bruto_srd']:.2f}",
                f"{emp['amount_bijz_bruto_srd']:.2f}",
                f"{emp['amount_uitk_ineens_srd']:.2f}",
                f"{emp['amount_overwerk_150_srd']:.2f}",
                f"{emp['amount_overwerk_200_srd']:.2f}",
                f"{emp['amount_akb_srd']:.2f}",
                f"{emp['amount_belastingvrij_periode_srd']:.2f}",
                f"{emp['amount_aov_art14_srd']:.2f}",
                f"{emp['amount_aov_bijz_srd']:.2f}",
                f"{emp['amount_aov_17a_srd']:.2f}",
                f"{emp['amount_aov_overwerk_srd']:.2f}",
                f"{emp['amount_aov_srd']:.2f}",
                f"{emp['amount_lb_art14_srd']:.2f}",
                f"{emp['amount_lb_bijz_srd']:.2f}",
                f"{emp['amount_lb_17a_srd']:.2f}",
                f"{emp['amount_lb_overwerk_srd']:.2f}",
                f"{emp['amount_lb_srd']:.2f}",
                f"{emp['amount_netto_srd']:.2f}",
            ])
        return buffer.getvalue().encode('utf-8-sig')

    def _get_export_filename(self):
        self.ensure_one()
        company_slug = re.sub(r'[^0-9A-Za-z]+', '_', self.company_id.name or 'bedrijf').strip('_').lower()
        return f'verzamelloonstaat_{self.year}_{company_slug}.csv'

    def _check_missing_cribnr(self, employees):
        missing = [e['employee_name'] for e in employees if not e['cribnr']]
        if missing:
            return (
                f'Let op: {len(missing)} werknemer(s) zonder CRIB-nummer. '
                'Vul het ID-nummer in bij de werknemersgegevens voor een correcte aangifte: '
                + ', '.join(missing[:5])
                + ('…' if len(missing) > 5 else '')
            )
        return False

    def action_export_csv(self):
        self.ensure_one()
        records = self._get_annual_records()
        if not records:
            raise UserError(
                f'Geen afgeronde SR-loonstroken gevonden voor {self.company_id.name} '
                f'in boekjaar {self.year}. Controleer of de loonstroken zijn bevestigd (done/paid).'
            )
        employees = self._aggregate_by_employee(records)
        warning = self._check_missing_cribnr(employees)
        payload = self._build_csv_payload(employees)
        filename = self._get_export_filename()
        self.write({
            'row_count': len(employees),
            'export_filename': filename,
            'export_file': b64encode(payload),
            'warning_message': warning or False,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': (
                '/web/content?model=%s&id=%s&field=export_file'
                '&download=true&filename_field=export_filename'
                % (self._name, self.id)
            ),
            'target': 'self',
        }
