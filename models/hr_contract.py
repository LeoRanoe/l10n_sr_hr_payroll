# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as Date

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import sr_artikel14_calculator as calc


class HrContract(models.Model):
    _inherit = 'hr.contract'

    SR_AKB_MAX_CHILDREN = 4

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', '1 lb sal ovw (Maandloon)'),
            ('fn', 'FN (Fortnight)'),
        ],
        string='Surinaams Loontype',
        default='monthly',
        store=True,
        help='Selecteer het betaaltype: maandloon (12 periodes) of fortnight (26 periodes per jaar).',
    )

    sr_aantal_kinderen = fields.Integer(
        string='Aantal Kinderen',
        default=0,
        store=True,
        help=(
            'Aantal kinderen waarvoor kinderbijslag wordt betaald.\n'
            'Gebruikt voor de Art. 10h splitsing: max SRD 250/kind/maand, '
            'max SRD 1.000/maand is belastingvrij. Het meerdere is belastbaar.'
        ),
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
            '• Pensioenpremie en Art. 10f inhoudingen → Aftrek Belastingvrij\n'
            '• Overige netto-inhoudingen (ziektekosten, lening, vakbond) → Inhouding\n\n'
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
    sr_preview_breakdown_html = fields.Html(
        string='Berekeningsdetail',
        compute='_compute_sr_preview',
        store=False,
        sanitize=False,
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
        'sr_aantal_kinderen',
        'sr_vaste_regels.type_id',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.sr_categorie',
        'sr_vaste_regels.amount_type',
        'sr_vaste_regels.percentage',
        'sr_vaste_regels.percentage_base',
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
            heffingskorting = contract._sr_get_heffingskorting_per_periode()

            belastbaar_toelagen = contract._sr_resolve_regels('belastbaar')
            vrijgesteld_toelagen = contract._sr_resolve_other_vrijgestelde_regels()
            inhoudingen = contract._sr_resolve_regels('inhouding')
            aftrek_bv = contract._sr_resolve_regels('aftrek_belastingvrij')

            # Kinderbijslag splitsing (Art. 10h)
            kb_split = contract._sr_kinderbijslag_split()
            kb_belastbaar = kb_split['belastbaar']
            kb_vrijgesteld = kb_split['vrijgesteld']

            # Bruto belastbaar = salaris + belastbare toelagen + KB belastbaar
            bruto_belastbaar = (contract.wage or 0.0) + belastbaar_toelagen + kb_belastbaar
            result = calc.calculate_lb(
                bruto_belastbaar, periodes, params,
                aftrek_bv_per_periode=aftrek_bv,
            )

            bruto_totaal = (contract.wage or 0.0) + belastbaar_toelagen + kb_belastbaar + kb_vrijgesteld + vrijgesteld_toelagen
            contract.sr_preview_bruto = bruto_totaal
            contract.sr_preview_belastbaar_jaar = result['belastbaar_jaar']
            contract.sr_preview_lb_periode = result['lb_per_periode']
            contract.sr_preview_aov_periode = result['aov_per_periode']
            contract.sr_preview_netto = (
                bruto_totaal
                + heffingskorting
                - result['lb_per_periode']
                - result['aov_per_periode']
                - inhoudingen
                - aftrek_bv
            )
            contract.sr_preview_breakdown_html = calc.generate_breakdown_html(
                result=result,
                wage=contract.wage or 0.0,
                periodes=periodes,
                salary_type=contract.sr_salary_type,
                kb_split=kb_split,
                vrijgesteld=vrijgesteld_toelagen,
                inhoudingen=inhoudingen,
                belastbaar_toelagen=belastbaar_toelagen,
                bruto_totaal=bruto_totaal,
                netto_totaal=contract.sr_preview_netto,
                heffingskorting=heffingskorting,
            )

    @api.onchange('sr_aantal_kinderen')
    def _onchange_sr_aantal_kinderen(self):
        if self.sr_aantal_kinderen is False:
            return
        if self.sr_aantal_kinderen < 0:
            self.sr_aantal_kinderen = 0
            return {
                'warning': {
                    'title': 'Ongeldige AKB invoer',
                    'message': 'Aantal kinderen kan niet negatief zijn. De waarde is teruggezet naar 0.',
                }
            }
        if self.sr_aantal_kinderen > self.SR_AKB_MAX_CHILDREN:
            self.sr_aantal_kinderen = self.SR_AKB_MAX_CHILDREN
            return {
                'warning': {
                    'title': 'AKB limiet bereikt',
                    'message': 'Voor de 2026 release accepteert de module maximaal 4 kinderen voor AKB.',
                }
            }

    @api.onchange('wage')
    def _onchange_wage_non_negative(self):
        if self.wage is not False and self.wage < 0:
            self.wage = 0.0
            return {
                'warning': {
                    'title': 'Ongeldig loonbedrag',
                    'message': 'Negatieve lonen zijn niet toegestaan. Het basisloon is teruggezet naar SRD 0,00.',
                }
            }

    @api.constrains('wage')
    def _check_non_negative_wage(self):
        for contract in self:
            if contract.wage < 0:
                raise ValidationError('Negatieve lonen zijn niet toegestaan op Surinaamse contracten.')

    @api.constrains('sr_aantal_kinderen')
    def _check_sr_aantal_kinderen_range(self):
        for contract in self:
            if contract.sr_aantal_kinderen < 0:
                raise ValidationError('Aantal kinderen kan niet negatief zijn.')
            if contract.sr_aantal_kinderen > self.SR_AKB_MAX_CHILDREN:
                raise ValidationError(
                    'Aantal kinderen voor AKB mag voor de 2026 release maximaal 4 zijn.'
                )

    @api.depends()
    def _compute_sr_tax_bracket_html(self):
        """Genereert de Art. 14 tarieftabel HTML uit actuele parameters."""
        today = Date.today()
        params = calc.fetch_params_from_rule_parameter(self.env, today)
        html = calc.generate_tax_bracket_html(params)
        for contract in self:
            contract.sr_tax_bracket_html = html

    # ── Helper methoden voor berekeningen ──────────────────────────────

    def _sr_get_heffingskorting_per_periode(self, heffingskorting_maand=None):
        """Geeft de netto heffingskorting terug voor maandloon of FN."""
        self.ensure_one()
        if heffingskorting_maand is None:
            heffingskorting_maand = calc.get_sr_parameter_value(
                self.env, 'SR_HEFFINGSKORTING', Date.today(),
                default=750.0, raise_if_not_found=False,
            )
        if not heffingskorting_maand:
            return 0.0

        periodes = 26 if self.sr_salary_type == 'fn' else 12
        if periodes == 12:
            return calc.round_money(heffingskorting_maand)
        return calc.round_money(heffingskorting_maand * 12.0 / 26.0)

    def _sr_resolve_line_amount(self, line):
        """
        Berekent het effectieve bedrag van een vaste loon regel.

        Handelt zowel vaste bedragen als percentages af.
        Bij percentage: berekend over basisloon of bruto belastbaar.
        """
        if line.amount_type == 'percentage' and line.percentage:
            if line.percentage_base == 'bruto_belastbaar':
                base = (self.wage or 0.0) + sum(
                    l.amount or 0.0 for l in self.sr_vaste_regels
                    if l._sr_effective_category() == 'belastbaar'
                    and l.amount_type != 'percentage'
                    and l.id != line.id
                )
            else:
                base = self.wage or 0.0
            return base * (line.percentage / 100.0)
        return line.amount or 0.0

    def _sr_resolve_regels(self, categorie):
        """
        Totale bedrag van vaste regels voor een bepaalde categorie.

        Handelt percentages automatisch af via _sr_resolve_line_amount.
        """
        return sum(
            self._sr_resolve_line_amount(r) for r in self.sr_vaste_regels
            if r._sr_effective_category() == categorie
        )

    def _sr_resolve_other_vrijgestelde_regels(self):
        """Totale vrijgestelde contractregels exclusief kinderbijslag (Art. 10h)."""
        return sum(
            self._sr_resolve_line_amount(r) for r in self.sr_vaste_regels
            if r._sr_effective_category() == 'vrijgesteld' and not r._is_sr_kindbijslag_line()
        )

    def _sr_kinderbijslag_split(self, max_kind_maand=None, max_maand=None):
        """
        Splitst kinderbijslag in belastbaar en vrijgesteld deel (Art. 10h).

        Wanneer max_kind_maand of max_maand None is, wordt de waarde
        automatisch opgehaald uit System Parameters met fallback naar
        hr.rule.parameter.

        :param max_kind_maand: Maximum vrijstelling per kind per maand (SRD)
        :param max_maand: Maximum vrijstelling per maand (SRD)
        :returns: dict met 'belastbaar' en 'vrijgesteld'
        """
        if max_kind_maand is None:
            max_kind_maand = calc.get_sr_parameter_value(
                self.env, 'SR_KINDBIJ_MAX_KIND_MAAND', Date.today(),
                default=250.0, raise_if_not_found=False,
            )
        if max_maand is None:
            max_maand = calc.get_sr_parameter_value(
                self.env, 'SR_KINDBIJ_MAX_MAAND', Date.today(),
                default=1000.0, raise_if_not_found=False,
            )
        # Kinderbijslag regels via type KINDBIJ of genormaliseerde naam.
        kb_lines = [
            r for r in self.sr_vaste_regels
            if r._is_sr_kindbijslag_line()
        ]
        total_kb = sum(self._sr_resolve_line_amount(r) for r in kb_lines) if kb_lines else 0.0

        if total_kb <= 0:
            return {'belastbaar': 0.0, 'vrijgesteld': 0.0}

        if not self.sr_aantal_kinderen or self.sr_aantal_kinderen <= 0:
            # Geen kinderen geregistreerd: volledige KB is belastbaar
            return {'belastbaar': total_kb, 'vrijgesteld': 0.0}

        periodes = 26 if self.sr_salary_type == 'fn' else 12
        exempt_maand = min(self.sr_aantal_kinderen * max_kind_maand, max_maand)
        exempt_per_periode = exempt_maand if periodes == 12 else exempt_maand * 12.0 / 26.0

        kb_exempt = min(total_kb, exempt_per_periode)
        kb_belastbaar = max(0.0, total_kb - exempt_per_periode)

        return {'belastbaar': kb_belastbaar, 'vrijgesteld': kb_exempt}

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
                ('date_start', '<=', date_stop),
                ('date_stop', '>=', date_start),
            ])
            if existing:
                # Delete with admin context to bypass validation restrictions
                existing.sudo().unlink()
        
        # Call parent implementation
        return super().generate_work_entries(date_start, date_stop, force=force)
