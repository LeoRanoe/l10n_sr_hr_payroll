# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as Date

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import sr_artikel14_calculator as calc


class HrContract(models.Model):
    _inherit = 'hr.contract'

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', 'Maandloon (12× per jaar)'),
            ('fn', 'Fortnight Loon (26× per jaar)'),
        ],
        string='Surinaams Loontype',
        default='monthly',
        help='Selecteer het betaaltype: maandloon (12 periodes) of fortnight (26 periodes per jaar).',
    )

    # ── Flexibele vaste loon regels (debit / credit) ───────────────────────
    sr_vaste_regels = fields.One2many(
        comodel_name='hr.contract.sr.line',
        inverse_name='contract_id',
        string='Vaste Loon Regels',
        help=(
            'Vaste bedragen die elke loonperiode verwerkt worden.\n\n'
            'Voeg hier toe:\n'
            '• Toeslagen (olie, kleding, representatie, ...) → Belastbaar of Belastingvrij\n'
            '• Inhoudingen (pensioenpremie, ziektekostenpremie, ...) → Inhouding\n\n'
            'Voor eenmalige of variabele bedragen (overwerk, vakantietoelage, bonus): '
            'gebruik de Payslip inputs bij het aanmaken van de loonstrook.'
        ),
    )

    # ── Rekenvoorbeeld — live Artikel 14 preview ──────────────────────────
    sr_preview_bruto = fields.Monetary(
        string='Bruto Loon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_belastbaar_jaar = fields.Monetary(
        string='Belastbaar Jaarloon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_lb_periode = fields.Monetary(
        string='Loonbelasting per Periode',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_aov_periode = fields.Monetary(
        string='AOV per Periode',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_netto = fields.Monetary(
        string='Geschat Nettoloon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )

    # ── Dynamische tarieftabel (uit parameters) ────────────────────────────
    sr_tax_bracket_html = fields.Html(
        string='Tariefschijven',
        compute='_compute_sr_tax_bracket_html',
        store=False,
        sanitize=False,
    )

    @api.depends(
        'wage',
        'sr_salary_type',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.sr_categorie',
    )
    def _compute_sr_preview(self):
        """
        Berekent Art. 14 loonbelasting preview op basis van contractwaarden.

        Gebruikt de centrale sr_artikel14_calculator zodat preview altijd
        overeenkomt met de werkelijke payslip berekening.
        """
        today = Date.today()
        params = calc.fetch_params_from_rule_parameter(self.env, today)

        for contract in self:
            periodes = 26 if contract.sr_salary_type == 'fn' else 12

            belastbaar_toelagen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'belastbaar'
            )
            vrijgesteld_toelagen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'vrijgesteld'
            )
            inhoudingen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'inhouding'
            )

            bruto_belastbaar = (contract.wage or 0.0) + belastbaar_toelagen
            result = calc.calculate_lb(bruto_belastbaar, periodes, params)

            bruto_totaal = bruto_belastbaar + vrijgesteld_toelagen
            contract.sr_preview_bruto = bruto_totaal
            contract.sr_preview_belastbaar_jaar = result['belastbaar_jaar']
            contract.sr_preview_lb_periode = result['lb_per_periode']
            contract.sr_preview_aov_periode = result['aov_per_periode']
            contract.sr_preview_netto = bruto_totaal - result['lb_per_periode'] - result['aov_per_periode'] - inhoudingen

    @api.depends()
    def _compute_sr_tax_bracket_html(self):
        """Genereert de Art. 14 tarieftabel HTML uit actuele parameters."""
        today = Date.today()
        params = calc.fetch_params_from_rule_parameter(self.env, today)
        html = calc.generate_tax_bracket_html(params)
        for contract in self:
            contract.sr_tax_bracket_html = html

    def generate_work_entries(self, date_start, date_stop, force=False):
        """
        Override: Allow admin/dev users to regenerate validated work entries.
        
        Base Odoo restricts regenerating validated work entries. This override
        allows System Admins (in the 'base.group_system' group) to bypass this
        restriction for testing and corrective work.
        
        :param date_start: Work entry period start
        :param date_stop: Work entry period stop
        :param force: Force deletion of existing entries (for admins)
        :return: Created work entry recordset
        """
        # Check if user is System Admin
        is_admin = self.env.user.has_group('base.group_system')
        
        if is_admin and force:
            # Allow admin to delete validated entries and regenerate
            existing = self.env['hr.work.entry'].search([
                ('contract_id', 'in', self.ids),
                ('date_start', '>=', date_start),
                ('date_stop', '<=', date_stop),
            ])
            if existing:
                # Delete with admin context to bypass validation restrictions
                existing.sudo().unlink()
        
        # Call parent implementation
        return super().generate_work_entries(date_start, date_stop, force=force)
