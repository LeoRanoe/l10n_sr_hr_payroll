# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Bankexport Wizard — Salarisbetaling Betaalbestand Suriname
==========================================================
Genereert betaalbestanden voor Surinaamse banken op basis van een loonrun.

Ondersteunde banken:
- De Surinaamsche Bank (DSB)  : CSV puntkomma-gescheiden
- Hakrinbank                  : TXT tab-gescheiden (BOA)
- Finabank N.V.               : CSV komma-gescheiden
- Republic Bank Suriname      : CSV puntkomma-gescheiden
- Generiek / Overig           : CSV met alle kolommen

Vereisten:
- Werknemer heeft een bankrekening (Werknemer → Privé-informatie → Bankrekeningen)
- Loonrun bevat bevestigde loonstroken (status Done of Paid)
"""

from base64 import b64encode
import csv
from datetime import date
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
        default='generic',
        help='Selecteer de bank waarvoor het betaalbestand wordt gegenereerd.',
    )
    debit_account = fields.Char(
        string='Rekeningnr. werkgever (debet)',
        required=True,
        help='Rekeningnummer van de werkgever waarvan de salarissen worden afgeschreven.',
    )
    payment_date = fields.Date(
        string='Betaaldatum',
        required=True,
        default=fields.Date.today,
        help='Datum waarop de overboekingen worden uitgevoerd.',
    )
    payment_reference = fields.Char(
        string='Betalingsomschrijving',
        help='Omschrijving die op de afschriften van werknemers verschijnt.',
    )

    # Resultaatvelden (readonly, zichtbaar na genereren)
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
        """Haalt netto-salarissen op per werknemer uit de loonrun."""
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
                'Zorg dat de loonstroken de status Bevestigd of Betaald hebben.'
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

            if not acc_number:
                missing_bank.append(rec.employee_name or (emp.name if emp else '?'))

            result.append({
                'employee_name': rec.employee_name or (emp.name if emp else '-'),
                'account_number': acc_number,
                'bank_name': bank_name,
                'amount': rec.amount_netto_srd or 0.0,
            })

        return result, missing_bank

    def _fmt_amount(self, value):
        """Bedrag als decimaal getal met punt (internationale bankstandaard)."""
        return f'{value:.2f}'

    def _fmt_date(self):
        """Datum als DD-MM-YYYY."""
        d = self.payment_date or date.today()
        return d.strftime('%d-%m-%Y')

    # ── DSB betaalbestand ────────────────────────────────────────────────────
    def _build_dsb_payload(self, records, reference, run):
        """
        De Surinaamsche Bank (DSB) — CSV puntkomma-gescheiden.
        Kolommen: Betaaldatum ; Debitering ; Creditering ; Naam ; Bedrag ; Valuta ; Omschrijving
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow([
            'Betaaldatum',
            'Rekeningnr. debet (werkgever)',
            'Rekeningnr. credit (werknemer)',
            'Naam werknemer',
            'Bedrag',
            'Valuta',
            'Omschrijving',
        ])
        for r in records:
            w.writerow([
                self._fmt_date(),
                self.debit_account or '',
                r['account_number'],
                r['employee_name'],
                self._fmt_amount(r['amount']),
                'SRD',
                reference,
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Hakrinbank BOA betaalbestand ─────────────────────────────────────────
    def _build_hakrinbank_payload(self, records, reference, run):
        """
        Hakrinbank — BOA (Betaalopdrachten Applicatie) TAB-gescheiden TXT.
        Kolommen (geen header): Datum [TAB] Debet [TAB] Credit [TAB] Naam [TAB] Bedrag [TAB] Valuta [TAB] Omschrijving
        """
        buf = StringIO()
        for r in records:
            line = '\t'.join([
                self._fmt_date(),
                self.debit_account or '',
                r['account_number'],
                r['employee_name'],
                self._fmt_amount(r['amount']),
                'SRD',
                reference,
            ])
            buf.write(line + '\r\n')
        return buf.getvalue().encode('utf-8'), 'txt'

    # ── Finabank betaalbestand ───────────────────────────────────────────────
    def _build_finabank_payload(self, records, reference, run):
        """
        Finabank N.V. — CSV komma-gescheiden.
        Kolommen: PaymentDate, DebitAccount, CreditAccount, BeneficiaryName, Amount, Currency, Reference
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=',', quoting=csv.QUOTE_ALL)
        w.writerow([
            'PaymentDate',
            'DebitAccount',
            'CreditAccount',
            'BeneficiaryName',
            'Amount',
            'Currency',
            'Reference',
        ])
        for r in records:
            w.writerow([
                self._fmt_date(),
                self.debit_account or '',
                r['account_number'],
                r['employee_name'],
                self._fmt_amount(r['amount']),
                'SRD',
                reference,
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Republic Bank betaalbestand ──────────────────────────────────────────
    def _build_republic_bank_payload(self, records, reference, run):
        """
        Republic Bank Suriname — CSV puntkomma-gescheiden.
        Kolommen: payment_date ; debit_account ; credit_account ; beneficiary_name ; amount ; currency ; reference
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow([
            'payment_date',
            'debit_account',
            'credit_account',
            'beneficiary_name',
            'amount',
            'currency',
            'reference',
        ])
        for r in records:
            w.writerow([
                self._fmt_date(),
                self.debit_account or '',
                r['account_number'],
                r['employee_name'],
                self._fmt_amount(r['amount']),
                'SRD',
                reference,
            ])
        return buf.getvalue().encode('utf-8-sig'), 'csv'

    # ── Generiek betaalbestand ───────────────────────────────────────────────
    def _build_generic_payload(self, records, reference, run):
        """
        Generiek betaalbestand — volledige informatie, geschikt voor elke bank.
        CSV puntkomma-gescheiden met alle kolommen.
        """
        buf = StringIO()
        w = csv.writer(buf, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        w.writerow([
            'Betaaldatum',
            'Rekeningnr. debet (werkgever)',
            'Rekeningnr. credit (werknemer)',
            'Naam werknemer',
            'Bank werknemer',
            'Bedrag (SRD)',
            'Valuta',
            'Omschrijving',
        ])
        for r in records:
            w.writerow([
                self._fmt_date(),
                self.debit_account or '',
                r['account_number'],
                r['employee_name'],
                r['bank_name'],
                self._fmt_amount(r['amount']),
                'SRD',
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
                f'{len(missing_bank)} werknemer(s) missen een bankrekeningnummer '
                '(Werknemer → Privé-informatie → Bankrekeningen): '
                + ', '.join(missing_bank[:5])
                + ('…' if len(missing_bank) > 5 else '')
            )

        # Sla bestand op als bijlage voor betrouwbare download
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas': b64encode(payload).decode(),
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })

        self.write({
            'row_count': len(records),
            'total_amount': sum(r['amount'] for r in records),
            'missing_bank_count': len(missing_bank),
            'export_filename': filename,
            'warning_message': warning or False,
        })

        # Bestand downloaden + dialoog open houden via twee acties
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
