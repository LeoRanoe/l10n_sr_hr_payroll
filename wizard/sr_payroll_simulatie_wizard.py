# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models

from ..models import sr_artikel14_calculator as calc


class SrPayrollSimulatieWizard(models.TransientModel):
    _name = 'sr.payroll.simulatie.wizard'
    _description = 'SR Netto Loon Simulatie'

    loontype = fields.Selection([
        ('maandloon', 'Maandloon (12 periodes)'),
        ('fn', 'FN-loon (26 periodes)'),
    ], string='Loontype', required=True, default='maandloon')
    brutoloon = fields.Float(string='Brutoloon per periode', required=True)
    toelagen = fields.Float(string='Belastbare toelagen', default=0.0)
    aantal_kinderen = fields.Integer(string='Aantal kinderen', default=0)

    beroepskosten = fields.Float(string='Beroepskosten (Art. 12)', compute='_compute_berekeningen')
    belastbaar_jaar = fields.Float(string='Belastbaar jaarloon', compute='_compute_berekeningen')
    art14_loonbelasting = fields.Float(string='Art. 14 Loonbelasting', compute='_compute_berekeningen')
    aov = fields.Float(string='AOV bijdrage', compute='_compute_berekeningen')
    kinderbijslag = fields.Float(string='Kinderbijslag', compute='_compute_berekeningen')
    netto = fields.Float(string='Netto loon', compute='_compute_berekeningen')

    @api.depends('brutoloon', 'loontype', 'aantal_kinderen', 'toelagen')
    def _compute_berekeningen(self):
        for record in self:
            if not record.brutoloon:
                record.beroepskosten = 0.0
                record.belastbaar_jaar = 0.0
                record.art14_loonbelasting = 0.0
                record.aov = 0.0
                record.kinderbijslag = 0.0
                record.netto = 0.0
                continue

            periodes = 26 if record.loontype == 'fn' else 12
            bruto_voor_belasting = record.brutoloon + record.toelagen

            try:
                params = calc.fetch_params_from_rule_parameter(record.env, date.today())
                result = calc.calculate_lb(bruto_voor_belasting, periodes, params)
            except Exception:
                record.beroepskosten = 0.0
                record.belastbaar_jaar = 0.0
                record.art14_loonbelasting = 0.0
                record.aov = 0.0
                record.kinderbijslag = 0.0
                record.netto = 0.0
                continue

            kinderen = min(record.aantal_kinderen, 4)
            kindbij_per_kind = calc.get_sr_parameter_value(
                record.env, 'SR_KINDBIJ_MAX_KIND_MAAND', date.today(), default=250.0,
            )
            kinderbijslag = kinderen * kindbij_per_kind

            record.beroepskosten = result['forfaitaire_per_periode']
            record.belastbaar_jaar = result['belastbaar_jaar']
            record.art14_loonbelasting = result['lb_per_periode']
            record.aov = result['aov_per_periode']
            record.kinderbijslag = kinderbijslag
            record.netto = (
                bruto_voor_belasting
                + kinderbijslag
                - result['lb_per_periode']
                - result['aov_per_periode']
            )

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_sr_hr_payroll.action_report_sr_payroll_simulatie'
        ).report_action(self)
