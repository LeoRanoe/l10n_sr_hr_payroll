# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Bankexport Wizard — Salarisbetaling Betaalbestand Suriname
==========================================================
Genereert betaalbestanden voor de Surinaamse banken op basis van een loonrun.

Ondersteunde banken en formaten (gebaseerd op bankeigen standaarden):
- De Surinaamsche Bank (DSB)  : CSV puntkomma-gescheiden (Advanced Online Banking)
- Hakrinbank                  : TXT tab-gescheiden (BOA — Betaalopdrachten Applicatie)
- Finabank N.V.               : CSV komma-gescheiden (Corporate Online Banking)
- Republic Bank Suriname      : CSV puntkomma-gescheiden (RepublicOnline)
- Generiek / Overig           : CSV met volledige informatiekolommen

Vereisten:
- Werknemer moet een bankrekening hebben (Werknemer → Privé-informatie → Bankrekening)
- Loonrun moet bevestigde loonstroken bevatten (status Done of Paid)
"""

from base64 import b64encode
import csv
from io import StringIO
import re

from odoo import api, fields, models
from odoo.exceptions import UserError


_BANK_FORMATS = [
    ('dsb', 'De Surinaamsche Bank (DSB)'),
    ('hakrinbank', 'Hakrinbank'),
    ('finabank', 'Finabank N.V.'),
    ('republic_bank', 'Republic Bank Suriname'),
    ('generic', 'Generiek / Overig'),
]

_BANK_SLUGS = {k: v for k, v in _BANK_FORMATS}


class SrPayrollBankExportWizard(models.TransientModel):
    _name = 'sr.payroll.bank.export.wizard'
    _description = 'SR Bankexport — Salarisbetaling Betaalbestand'

    company_id = fields.Many2one(
        'res.company',
        string='Bedrijf',
        required=True,
        default=lambda self: self.env.company,
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Loonrun',
        required=True,
        domain="[('company_id', '=', company_id)]",
        help='Selecteer de loonrun waarvoor het betaalbestand wordt aangemaakt.',
    )
    bank_format = fields.Selection(
        _BANK_FORMATS,
        string='Bank / Formaat',
        required=True,
        default='dsb',
        help=(
            'Selecteer de bank waarvoor het betaalbestand wordt gegenereerd. '
            'Elk formaat is afgestemd op de upload-specificaties van die bank.'
        ),
    )
    debit_account = fields.Char(
        string='Rekeningnr. werkgever (debet)',
        help='Rekeningnummer van de werkgever waarvan de salarissen worden afgeschreven.',
    )
    payment_reference = fields.Char(
        string='Betalingsomschrijving',
        help='Omschrijving die op de afschriften van werknemers verschijnt, bijv. "Salaris Mei 2026".',
    )
    # Result fields (readonly)
    row_count = fields.Integer(string='Aantal werknemers', readonly=True)
    total_amount = fields.Float(string='Totaal netto (SRD)', readonly=True, digits=(16, 2))
    missing_bank_count = fields.Integer(string='Zonder bankrekening', readonly=True)
    warning_message = fields.Char(string='Waarschuwing', readonly=True)
    export_file = fields.Binary(string='Betaalbestand', readonly=True, attachment=False)
    export_filename = fields.Char(string='Bestandsnaam', readonly=True)

    @api.onchange('payslip_run_id')
    def _onchange_payslip_run(self):
        if self.payslip_run_id and not self.payment_reference:
            self.payment_reference = f'Salaris {self.payslip_run_id.name}'

    def _get_payment_records(self):
        """
        Haalt netto-salarissen op uit de belastingrapportage view.
        Geeft (records_list, missing_bank_list) terug.
        """
        self.ensure_one()
        self.env.flush_all()

        run = self.payslip_run_id
        tax_records = self.env['hr.payroll.tax.report'].search([
            ('payslip_run_id', '=', run.id),
            ('company_id', '=', self.company_id.id),
            ('payslip_state', 'in', ['done', 'paid']),
        ], order='employee_name')

        if not tax_records:
            raise UserError(
                f'Geen bevestigde loonstroken gevonden in loonrun "{run.name}". '
                'Zorg dat de loonstroken bevestigd zijn (status: Gedaan of Betaald) '
                'voordat u het betaalbestand genereert.'
            )

        result = []
        missing_bank = []

        for rec in tax_records:
            emp = rec.employee_id
            bank_acc = emp.bank_account_id if emp else None
            acc_number = (bank_acc.acc_number or '').strip() if bank_acc else ''
            bank_name = ''
            if bank_acc and bank_acc.bank_id:
                bank_name = bank_acc.bank_id.name or ''
            elif bank_acc and hasattr(bank_acc, 'bank_name'):
                bank_name = bank_acc.bank_name or ''

            if not acc_number:
                missing_bank.append(rec.employee_name or (emp.name if emp else '?'))

            result.append({
                'employee_name': rec.employee_name or (emp.name if emp else '-'),
                'account_number': acc_number,
                'bank_name': bank_name,
                'amount_srd': rec.amount_netto_srd or 0.0,
            })

        return result, missing_bank

    # ── DSB betaalbestand ────────────────────────────────────────────────────
    def _build_dsb_payload(self, records, reference, run):
        """
        De Surinaamsche Bank (DSB) — Advanced Online Banking batch betaalbestand.
        Formaat: CSV puntkomma-gescheiden.
        Conform DSB file upload specificatie (Excel-template equivalent).
        Velden: Rekeningnummer ; Naam begunstigde ; Bedrag ; Valuta ; Omschrijving
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow(['Rekeningnummer', 'Naam begunstigde', 'Bedrag', 'Valuta', 'Omschrijving'])
        for r in records:
            w.writerow([
                r['account_number'],
                r['employee_name'],
                f"{r['amount_srd']:.2f}".replace('.', ','),
                'SRD',
                reference,
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Hakrinbank BOA betaalbestand ─────────────────────────────────────────
    def _build_hakrinbank_payload(self, records, reference, run):
        """
        Hakrinbank — BOA (Betaalopdrachten Applicatie) importbestand.
        Formaat: TAB-gescheiden TXT bestand conform Hakrinbank BOA import standaard.
        Hakrinbank BOA accepteert meerdere bestandstypen; dit is het TXT-formaat.
        Geen header — Hakrinbank BOA leest velden op positie.
        Velden: Rekeningnr [TAB] Naam [TAB] Bedrag [TAB] Valuta [TAB] Omschrijving [TAB] Referentie
        """
        buf = StringIO()
        for r in records:
            line = '\t'.join([
                r['account_number'],
                r['employee_name'],
                f"{r['amount_srd']:.2f}",
                'SRD',
                reference,
                f"Loon {run.name}",
            ])
            buf.write(line + '\r\n')
        return buf.getvalue().encode('utf-8'), 'txt'

    # ── Finabank betaalbestand ───────────────────────────────────────────────
    def _build_finabank_payload(self, records, reference, run):
        """
        Finabank N.V. — Corporate Online Banking betaalbestand.
        Formaat: CSV komma-gescheiden (conform Finabank Corporate Banking upload).
        Velden: AccountNumber, BeneficiaryName, Amount, Currency, Reference, Description
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=',', quoting=csv.QUOTE_ALL)
        w.writerow(['AccountNumber', 'BeneficiaryName', 'Amount', 'Currency', 'Reference', 'Description'])
        for r in records:
            w.writerow([
                r['account_number'],
                r['employee_name'],
                f"{r['amount_srd']:.2f}",
                'SRD',
                reference,
                f"Salaris {run.name}",
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Republic Bank betaalbestand ──────────────────────────────────────────
    def _build_republic_bank_payload(self, records, reference, run):
        """
        Republic Bank Suriname — RepublicOnline batch betaalbestand.
        Formaat: CSV puntkomma-gescheiden conform Republic Bank online portaal.
        Velden: account_number ; beneficiary_name ; amount ; currency ; reference ; description
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow(['account_number', 'beneficiary_name', 'amount', 'currency', 'reference', 'description'])
        for r in records:
            w.writerow([
                r['account_number'],
                r['employee_name'],
                f"{r['amount_srd']:.2f}",
                'SRD',
                reference,
                f"Salaris {run.name}",
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Generiek betaalbestand ───────────────────────────────────────────────
    def _build_generic_payload(self, records, reference, run):
        """
        Generiek betaalbestand — bruikbaar voor banken zonder specifiek formaat.
        Formaat: CSV puntkomma-gescheiden met volledige informatiekolommen.
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow([
            'Werknemer',
            'Bankrekeningnr.',
            'Bank',
            'Netto bedrag (SRD)',
            'Valuta',
            'Betalingsomschrijving',
            'Referentie',
        ])
        for r in records:
            w.writerow([
                r['employee_name'],
                r['account_number'],
                r['bank_name'],
                f"{r['amount_srd']:.2f}",
                'SRD',
                f"Salaris {run.name}",
                reference,
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    def action_export(self):
        self.ensure_one()
        records, missing_bank = self._get_payment_records()

        run = self.payslip_run_id
        reference = (self.payment_reference or f'Salaris {run.name}').strip()

        builders = {
            'dsb': self._build_dsb_payload,
            'hakrinbank': self._build_hakrinbank_payload,
            'finabank': self._build_finabank_payload,
            'republic_bank': self._build_republic_bank_payload,
            'generic': self._build_generic_payload,
        }
        builder = builders.get(self.bank_format, self._build_generic_payload)
        payload, ext = builder(records, reference, run)

        bank_slug = re.sub(r'[^0-9a-z]+', '_', _BANK_SLUGS.get(self.bank_format, 'bank').lower()).strip('_')
        run_slug = re.sub(r'[^0-9A-Za-z]+', '_', run.name or 'loonrun').strip('_').lower()
        filename = f'betaalbestand_{bank_slug}_{run_slug}.{ext}'

        warning = None
        if missing_bank:
            warning = (
                f'{len(missing_bank)} werknemer(s) zonder bankrekeningnummer — '
                'vul dit in via Werknemer → Privé-informatie → Bankrekeningen: '
                + ', '.join(missing_bank[:5])
                + ('…' if len(missing_bank) > 5 else '')
            )

        self.write({
            'row_count': len(records),
            'total_amount': sum(r['amount_srd'] for r in records),
            'missing_bank_count': len(missing_bank),
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
